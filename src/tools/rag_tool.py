import os

import faiss
import numpy as np
import polars as pl

# Imports LangChain
from langchain_community.vectorstores import PGVector
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings

# Imports Base de données
from sqlalchemy import create_engine, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

# 1. Imports propres depuis notre configuration centralisée (La source de vérité)
from src.config import EMBEDDING_MODEL_NAME, PARQUET_FILE_PATH, SUPABASE_URL

# 2. Import de tes tables
from supabase_db import ContentStore, Media, Score

# --- INITIALISATION DE LA CONNEXION ---
engine = create_engine(SUPABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def _resolve_media(session, reference: str):
    """Résout une référence (ID ou titre approximatif) vers UN film précis.

    Stratégie déterministe, dans cet ordre :
      1. Match EXACT par horragor_id ou par titre (insensible à la casse).
      2. À défaut, le PLUS COURT titre contenant la référence.
         Ainsi 'Alien' l'emporte sur 'Alienation', 'Alien Nation', etc.

    Remplace l'ancien `or_(...).ilike("%ref%").first()` qui, sans tri, attrapait
    le premier film physique venu (d'où 'Alienation' au lieu du vrai 'Alien').
    """
    ref = reference.strip()

    # 1. Match exact : ID unique OU titre complet (casse ignorée).
    media = (
        session.query(Media)
        .filter(
            or_(
                Media.horragor_id == ref,
                func.lower(Media.title) == ref.lower(),
            )
        )
        .first()
    )
    if media:
        return media

    # 2. Fallback : le titre le plus court qui CONTIENT la référence.
    #    order_by(length) puis horragor_id => résultat stable et déterministe.
    return (
        session.query(Media)
        .filter(Media.title.ilike(f"%{ref}%"))
        .order_by(func.length(Media.title).asc(), Media.horragor_id.asc())
        .first()
    )


# --- ROUTEUR FAISS (Classe isolée) ---
class FastMovieRouter:
    """Routeur vectoriel local pour valider l'existence d'un film."""

    def __init__(self, parquet_path: str = PARQUET_FILE_PATH):
        print("🧠 Initialisation de la mémoire éphémère (Routeur FAISS)...")
        self.embeddings_model = OllamaEmbeddings(model=EMBEDDING_MODEL_NAME)
        self.dimension = 768
        self.index = faiss.IndexFlatL2(self.dimension)
        self.movie_ids = []
        self.movie_titles = []
        self._load_and_index(parquet_path)

    def _load_and_index(self, parquet_path: str):
        index_file = "data/faiss_index.bin"
        if os.path.exists(index_file):
            print("⚡ Chargement du cache FAISS local...")
            self.index = faiss.read_index(index_file)
            if os.path.exists(parquet_path):
                df = pl.read_parquet(parquet_path)
                self.movie_ids = df["horragor_id"].to_list()
                self.movie_titles = df["title"].to_list()
            return

        print(
            "⚡ Aucun cache trouvé. Calcul des vecteurs FAISS (Cela peut prendre du temps)..."
        )
        if not os.path.exists(parquet_path):
            print("⚠️ Fichier Parquet introuvable pour FAISS.")
            return

        df = pl.read_parquet(parquet_path)
        self.movie_ids = df["horragor_id"].to_list()
        self.movie_titles = df["title"].to_list()

        for title in self.movie_titles:
            vector = self.embeddings_model.embed_query(str(title))
            self.index.add(np.array([vector], dtype=np.float32))

        faiss.write_index(self.index, index_file)
        print("✅ Index FAISS sauvegardé sur le disque !")

    def get_movie_id(self, query: str) -> str:
        """
        Convertit une requête textuelle en identifiant de film via similarité vectorielle (FAISS).

        Processus analytique :
        1. Vectorisation de la requête utilisateur (coordonnée spatiale).
        2. Recherche du plus proche voisin (Top 1) via la distance L2.
        3. Validation de la pertinence via un seuil de distance statique.

        ⚠️ Avertissement d'architecture : Le seuil statique (0.5) est arbitraire et
        dépend fortement du modèle d'embedding utilisé. Il risque de générer des faux
        négatifs si la dispersion du modèle 'nomic' est large.

        Args:
            query (str): L'intention ou la recherche textuelle brute.

        Returns:
            str | None: L'identifiant (horragor_id) si la distance < 0.5, sinon None.
        """
        # 1. Encodage mathématique de la requête
        vector = self.embeddings_model.embed_query(query)
        # 2. Recherche spatiale : D (Distances L2), indices FAISS en RAM
        D, indices = self.index.search(np.array([vector], dtype=np.float32), 1)
        # 3. Barrière de tolérance sémantique (Point de vulnérabilité à tester)
        if D[0][0] < 0.5:  # Seuil de tolérance
            # 4. Traduction de l'indice RAM vers l'identifiant de la base de données
            return self.movie_ids[indices[0][0]]
        # Fallback de sécurité si le vecteur est jugé hors-sujet
        return None


# -----------------------------------------------------
# --- OUTIL 1 : SQL (Fonction globale indépendante) ---
# -----------------------------------------------------
@tool
def query_movie_metadata(movie_reference: str) -> str:
    """
    Utilise cet outil pour obtenir les métadonnées d'un film.
    Tu peux lui fournir soit l'ID unique, soit directement le TITRE du film (ex: 'Alien').
    """
    print(f"  [SQL] Interrogation de Supabase pour : {movie_reference}...")
    session = SessionLocal()
    try:
        media = _resolve_media(session, movie_reference)

        if not media:
            return f"Aucune métadonnée trouvée en base pour '{movie_reference}'."

        # --- Présentation HONNÊTE des champs absents ---
        # budget/revenue sont des BigInteger default=0 : un 0 (ou None) signifie
        # "donnée absente", pas "budget nul". On l'affiche comme tel pour ne pas
        # que l'Écrivain (ni le CoT) prenne un 0 pour une vraie valeur.
        budget_str = f"{media.budget}$" if media.budget else "non renseigné"
        date_str = media.release_date if media.release_date else "non renseignée"

        score_record = session.query(Score).filter_by(media_id=media.id).first()
        note_str = (
            f"{score_record.value}/10"
            if score_record and score_record.value is not None
            else "non renseignée"
        )

        return (
            f"Titre Exact: {media.title}, Sortie: {date_str}, "
            f"Univers: {media.category}, Budget: {budget_str}, Note: {note_str}. "
            f"(ID officiel pour info: {media.horragor_id})"
        )
    except SQLAlchemyError as e:
        return f"Erreur SQL : {e!s}"
    finally:
        session.close()


# --- OUTIL 2 : PGVECTOR (Fonction globale indépendante) ---
@tool
def find_similar_horror_movies(movie_reference: str) -> str:
    """
    Utilise cet outil UNIQUEMENT pour recommander des films similaires.
    Tu peux lui fournir soit l'ID unique, soit directement le TITRE du film (ex: 'Alien').
    """
    print(f"   [PGVECTOR] Recherche de similarité pour : {movie_reference}...")
    session = SessionLocal()
    try:
        media = _resolve_media(session, movie_reference)

        if not media:
            return f"Film '{movie_reference}' introuvable pour la recommandation."

        content = session.query(ContentStore).filter_by(media_id=media.id).first()
        if not content or not content.synopsis:
            return f"Aucun synopsis pour {media.title}. Recommandation impossible."

        conn_string = SUPABASE_URL.replace("postgresql://", "postgresql+psycopg2://")

        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL_NAME)
        vectorstore = PGVector(
            connection_string=conn_string,
            collection_name="horragor_vectors",
            embedding_function=embeddings,
            use_jsonb=True,
        )

        results = vectorstore.similarity_search(content.synopsis, k=4)

        recommandations = [
            f"- {doc.page_content[:150]}..."
            for doc in results
            if media.title not in doc.page_content
        ]

        if not recommandations:
            return "Aucune similarité trouvée."

        return f"Recommandations basées sur '{media.title}' :\n" + "\n".join(
            recommandations
        )
    except SQLAlchemyError as e:
        return f"Erreur vectorielle : {e!s}"
    finally:
        session.close()
