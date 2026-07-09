import faiss
import wikipedia
import numpy as np
import polars as pl
import datetime
import requests
import os
from bs4 import BeautifulSoup
from typing import Annotated
from dotenv import load_dotenv

# --- IMPORTS POUR LA BASE DE DONNÉES RÉELLE ---
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from langchain_community.vectorstores import PGVector
from supabase_db import Media, Score, ContentStore  # Import du MPD exact

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

# Initialisation de la connexion SQL
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
if not SUPABASE_URL:
    raise ValueError("⚠️ La variable SUPABASE_URL est introuvable dans le fichier .env")

engine = create_engine(SUPABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# =====================================================================
# 1. LA MÉMOIRE ÉPHÉMÈRE : LE ROUTEUR FAISS
# =====================================================================
class FastMovieRouter:
    """
    Rôle : Cet index contient les couples [Nom du film : ID] mis en cache sur le disque.
    Usage : Valider l'existence d'un film et récupérer son identifiant unique instantanément.
    """

    def __init__(self, parquet_path: str, cache_dir="cache_faiss"):
        print("🧠 Initialisation de la mémoire éphémère (Routeur FAISS)...")
        self.embeddings_model = OllamaEmbeddings(model="nomic-embed-text")
        self.dimension = 768  # Dimension stricte pour nomic-embed-text

        self.index_path = os.path.join(cache_dir, "movies_titles.index")
        self.mapping_path = os.path.join(cache_dir, "movies_mapping.npy")

        self.movie_titles = []
        self.movie_ids = []

        # Créer le dossier de cache s'il n'existe pas
        os.makedirs(cache_dir, exist_ok=True)

        # STRATÉGIE DE CACHE : Si le fichier existe, on charge direct, sinon on calcule
        if os.path.exists(self.index_path) and os.path.exists(self.mapping_path):
            print("💾 Index FAISS détecté sur le disque. Chargement instantané...")
            self._load_from_cache()
        else:
            print("⚡ Aucun cache trouvé. Calcul initial des vecteurs...")
            self._load_and_index(parquet_path)

    def _load_and_index(self, parquet_path: str):
        try:
            df = pl.read_parquet(parquet_path)
            titles = df["title"].drop_nulls().to_list()
            ids = df["horragor_id"].drop_nulls().to_list()

            print(f"⚡ Calcul des vecteurs FAISS pour {len(titles)} titres (Ollama)...")
            vectors = self.embeddings_model.embed_documents(titles)

            vectors_np = np.array(vectors, dtype=np.float32)

            # Initialisation et remplissage de l'index FAISS
            self.index = faiss.IndexFlatL2(self.dimension)
            self.index.add(vectors_np)

            self.movie_titles = titles
            self.movie_ids = ids

            # --- SAUVEGARDE SUR LE DISQUE ---
            faiss.write_index(self.index, self.index_path)
            mapping_data = {"titles": self.movie_titles, "ids": self.movie_ids}
            np.save(self.mapping_path, mapping_data, allow_pickle=True)

            print(
                f"✅ Index FAISS opérationnel et sauvegardé sur le disque ({self.index.ntotal} films) !"
            )

        except Exception as e:
            print(f"⚠️ Erreur lors du calcul FAISS : {e}")

    def _load_from_cache(self):
        try:
            # 1. Rechargement de l'index binaire FAISS
            self.index = faiss.read_index(self.index_path)

            # 2. Rechargement des textes correspondants (Titres et IDs)
            mapping_data = np.load(self.mapping_path, allow_pickle=True).item()
            self.movie_titles = mapping_data["titles"]
            self.movie_ids = mapping_data["ids"]

            print(
                f"🚀 {self.index.ntotal} films chargés depuis le cache en 0.05 secondes !"
            )
        except Exception as e:
            print(
                f"⚠️ Erreur lors du chargement du cache FAISS : {e}. Recalcul nécessaire."
            )

    def get_movie_id(self, query_title: str) -> dict:
        """Méthode pour retrouver l'ID exact d'un film."""
        if not hasattr(self, "index") or self.index.ntotal == 0:
            return {"error": "Index non initialisé ou vide"}

        query_vector = np.array(
            [self.embeddings_model.embed_query(query_title)], dtype=np.float32
        )
        distances, indices = self.index.search(query_vector, k=1)

        match_idx = indices[0][0]
        # On passe de 1.5 à 0.6 ou 0.7 pour exiger une correspondance très forte
        if match_idx != -1 and distances[0][0] < 0.6: 
            return {
                "title": self.movie_titles[match_idx],
                "id": self.movie_ids[match_idx],
            }
        return {"error": "Film introuvable dans le routeur."}


# =====================================================================
# 2. LA BOÎTE À OUTILS DE L'AGENT (TOOLS SPECIFIQUES)
# =====================================================================


@tool
def query_movie_metadata(movie_id: str) -> str:
    """
    TOOL 1 : Requêtes SQL Spécialisées.
    Utilise cet outil pour obtenir les métadonnées exactes d'un film (réalisateur, année, budget, note).
    Tu DOIS LUI FOURNIR L'IDENTIFIANT UNIQUE DU FILM (movie_id) obtenu via le routeur (ex: '74a5b6...').
    """
    print(f"   [SQL] Interrogation de Supabase pour l'horragor_id : {movie_id}...")
    session = SessionLocal()
    try:
        # Requête SQL directe via SQLAlchemy basée sur NOTRE ID UNIQUE
        media = session.query(Media).filter_by(horragor_id=movie_id).first()
        if not media:
            return f"Aucune métadonnée trouvée en base pour l'ID '{movie_id}'."

        # Récupération de la note depuis la table enfant
        score_record = session.query(Score).filter_by(media_id=media.id).first()
        note = score_record.value if score_record else "Non renseignée"

        return (
            f"Métadonnées extraites de la base SQL : "
            f"Titre: {media.title}, Sortie: {media.release_date}, "
            f"Univers: {media.category}, Budget: {media.budget}$, Note globale: {note}/10."
        )
    except Exception as e:
        return f"Erreur lors de la requête SQL : {str(e)}"
    finally:
        session.close()


@tool
def find_similar_horror_movies(movie_id: str) -> str:
    """
    TOOL 2 : Le Recommandeur de Films Similaires.
    Utilise cet outil UNIQUEMENT si l'utilisateur demande des recommandations ou des films qui ressemblent à un autre.
    Tu DOIS LUI FOURNIR L'IDENTIFIANT UNIQUE DU FILM (movie_id).
    """
    print(f"   [PGVECTOR] Recherche de similarité cosinus pour l'ID : {movie_id}...")
    session = SessionLocal()
    try:
        # 1. On récupère le synopsis original du film ciblé dans la base de données
        media = session.query(Media).filter_by(horragor_id=movie_id).first()
        if not media:
            return (
                "Film introuvable dans la base, impossible de faire une recommandation."
            )

        content = session.query(ContentStore).filter_by(media_id=media.id).first()
        if not content or not content.synopsis:
            return f"Aucun synopsis enregistré pour {media.title}. Recommandation vectorielle impossible."

        synopsis_cible = content.synopsis

        # 2. On prépare la connexion vectorielle
        conn_string = SUPABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
        if conn_string.startswith("postgres://"):
            conn_string = conn_string.replace("postgres://", "postgresql+psycopg2://")

        embeddings = OllamaEmbeddings(model="nomic-embed-text")
        vectorstore = PGVector(
            connection_string=conn_string,
            collection_name="horragor_vectors",
            embedding_function=embeddings,
            use_jsonb=True,
        )

        # 3. Recherche de similarité sur la base du synopsis !
        results = vectorstore.similarity_search(synopsis_cible, k=4)

        if not results:
            return "Aucun film similaire trouvé dans la base vectorielle PGVector."

        # On ignore le film lui-même s'il remonte en première position
        recommandations = []
        for doc in results:
            if media.title not in doc.page_content:
                recommandations.append(f"- {doc.page_content[:150]}...")

        return (
            f"Recommandations sémantiques basées sur l'ADN du film '{media.title}' :\n"
            + "\n".join(recommandations)
        )

    except Exception as e:
        return f"Erreur de connexion à l'extension vectorielle : {str(e)}"
    finally:
        session.close()

@tool
def scrape_detailed_synopsis(movie_title: str) -> str:
    """
    TOOL 3 : Scraping On-Demand.
    Utilise cet outil SEULEMENT si l'utilisateur demande des anecdotes très précises, profondes ou un résumé complet.
    Fournis le titre COMPLET du film en argument texte.
    """
    print(f"   [WEB] API Wikipédia activée pour : {movie_title}...")
    try:
        # On force la langue française
        wikipedia.set_lang("fr")
        
        # 1. On effectue une vraie recherche pour trouver le titre exact de la page
        resultats_recherche = wikipedia.search(movie_title)
        
        if not resultats_recherche:
             return f"Aucune page Wikipédia trouvée pour le film '{movie_title}'."
             
        titre_officiel = resultats_recherche[0]
        
        # 2. On extrait le résumé proprement
        summary = wikipedia.summary(titre_officiel, sentences=4)
        return summary + "... [FIN DU SCRAPING]"
        
    except wikipedia.exceptions.DisambiguationError as e:
        # Gère le cas où plusieurs films ont le même nom
        return f"Le titre est trop ambigu. Wikipédia propose plusieurs pages : {e.options[:3]}"
    except Exception as e:
        return f"Erreur réseau ou page introuvable : {e}"


@tool
def calculate_movie_age(release_year: int) -> str:
    """
    TOOL 4 : Le Calculateur Temporel.
    Utilise cet outil pour calculer mathématiquement l'âge d'un film.
    Passe uniquement l'année de sortie à 4 chiffres (ex: 1979) en argument.
    """
    print(f"   [MATH] Calcul temporel pour l'année : {release_year}...")
    current_year = datetime.datetime.now().year
    age = current_year - int(release_year)
    return f"Le film a exactement {age} ans."


@tool
def horror_survival_simulator(synopsis: str) -> str:
    """
    TOOL 5 : Le Simulateur de Survie.
    Outil ludique. Utilise cet outil si l'utilisateur demande s'il survivrait dans le film.
    Passe un court résumé de l'intrigue en argument.
    """
    print("   [GAME] Lancement de la simulation de survie...")
    return "Simulation terminée. Probabilité de survie : 4%. Cause probable : Mort atroce dans l'espace ou une cabane."


# =====================================================================
# 3. ORCHESTRATION LANGGRAPH (LE CERVEAU REACT)
# =====================================================================
def create_horragor_agent(parquet_path: str):
    """Assemble l'agent LangGraph avec ses outils et son prompt système."""

    router = FastMovieRouter(parquet_path)

    tools = [
        query_movie_metadata,
        find_similar_horror_movies,
        scrape_detailed_synopsis,
        calculate_movie_age,
        horror_survival_simulator,
    ]

    llm = ChatOllama(model="llama3.2:3b", temperature=0.1)
    llm_with_tools = llm.bind_tools(tools)

    def node_agent(state: MessagesState):
        messages = state["messages"]
        if len(messages) > 0 and type(messages[-1]) == HumanMessage:
            user_query = messages[-1].content

            # ROUTAGE INTELLIGENT : On cherche l'ID en amont !
            route_data = router.get_movie_id(user_query)
            if "id" in route_data:
                # LA MAGIE DU PROMPT ENGINEERING : On donne les règles strictes au LLM
                system_hint = SystemMessage(
                    content=f"[INFO CACHÉE ROUTEUR FAISS] Le film détecté dans la question est '{route_data['title']}'. "
                    f"Son ID UNIQUE en base de données est : '{route_data['id']}'.\n"
                    f"RÈGLE 1 : Si tu utilises les outils 'query_movie_metadata' ou 'find_similar_horror_movies', "
                    f"tu DOIS utiliser l'ID '{route_data['id']}' comme argument.\n"
                    f"RÈGLE 2 : Si tu utilises l'outil 'scrape_detailed_synopsis', utilise le titre '{route_data['title']}'."
                )
                messages = [system_hint] + messages

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", node_agent)
    workflow.add_node("tools", ToolNode(tools))

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# --- POINT D'ENTRÉE POUR TESTER LOCALEMENT ---
if __name__ == "__main__":
    print("=" * 50)
    print("🦇 DÉMARRAGE DE L'AGENT HORRAGOR (Moteur ReAct) 🦇")
    print("=" * 50)

    fichier_parquet = "horragor_final_data.parquet"

    try:
        app = create_horragor_agent(fichier_parquet)
    except Exception as e:
        print(f"❌ Erreur critique au chargement de l'agent. Détail : {e}")
        exit(1)

    system_prompt = SystemMessage(
        content="Tu es HorRAGor, une entité cybernétique cinéphile sarcastique. Tu as accès à des outils. Pense étape par étape (ReAct)."
    )

    # Test d'une question qui déclenche le Tool SQL avec l'ID !
    query = (
        "Trouve les infos du film Interstellar dans notre base de données sécurisée."
    )

    inputs = {"messages": [system_prompt, HumanMessage(content=query)]}
    config = {"configurable": {"thread_id": "session_1"}}

    print(f"\nHumain : {query}\n")
    for s in app.stream(inputs, config, stream_mode="values"):
        message = s["messages"][-1]
        if message.type == "ai" and message.tool_calls:
            for tc in message.tool_calls:
                print(f"⚙️  [HorRAGor actionne l'outil] : {tc['name']} -> {tc['args']}")
        elif message.type == "tool":
            print(f"📥 [Résultat Outil SQL/Vectoriel] : {message.content}\n")

    print("\n🦇 Réponse finale de HorRAGor :")
    print(app.get_state(config).values["messages"][-1].content)
