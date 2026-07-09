import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

# Import LangChain pour structurer les messages
from langchain_core.messages import HumanMessage, SystemMessage

# 1. Imports de la configuration et du graphe officiel
from src.config import PARQUET_FILE_PATH
from src.graph.pipeline import app_graph

# Import de nos contrats de models
from src.models.chat_models import ChatRequest, ChatResponse  # noqa: F401
from src.tools.rag_tool import FastMovieRouter, SessionLocal  # noqa: F401

# On importe le modèle Media depuis le fichier de BDD de tes amis
from supabase_db import Media


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'API.
    """
    print("🚀 Démarrage du serveur FastAPI...")

    # 1. Test de la Base de données Supabase
    print("🔌 Tentative de ping sur la base de données Supabase (Gold)...")
    try:
        db = SessionLocal()
        movie_count = db.query(Media).count()
        print(f"✅ Connexion DB réussie ! {movie_count} films trouvés dans 'medias'.")
        db.close()
    except Exception as e:
        print(f"❌ Erreur critique lors de la connexion à la BDD : {e}")

    # 2. Chargement de la mémoire éphémère (Routeur FAISS)
    print("🧠 Chargement du Routeur FAISS en RAM...")
    try:
        # La classe FastMovieRouter (située dans rag_tool) contient sa propre logique :
        # Elle cherche le cache local sur le disque. S'il existe, elle le charge instantanément.
        # Sinon, elle recalcule et sauvegarde le fichier d'index automatiquement.
        app.state.movie_router = FastMovieRouter(PARQUET_FILE_PATH)
        print("✅ Index FAISS opérationnel (Persistance vérifiée) !")
    except Exception as e:
        print(f"❌ Erreur au chargement du routeur FAISS : {e}")

    # 3. Chargement du nouveau Multi-Agent LangGraph
    print("🧠 Chargement de l'architecture Multi-Agent HorRAGor v3.0...")
    try:
        # On assigne directement notre nouveau graphe compilé !
        app.state.agent = app_graph
        print("✅ Système Multi-Agent opérationnel !")
    except Exception as e:
        print(f"❌ Erreur critique au chargement de l'agent : {e}")

    yield
    print("🛑 Arrêt du serveur FastAPI.")


app = FastAPI(
    title="HorRAGor BOT API",
    description="API REST asynchrone branchée sur l'agent LangGraph et Supabase",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def health_check():
    """
    Route racine utilisée uniquement par l'interface Streamlit
    pour vérifier si l'API est en ligne (Ping).
    """
    return {"status": "L'entité HorRAGor est réveillée !"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint unique réceptionnant les questions de l'interface utilisateur.
    """
    start_time = time.time()

    if not hasattr(app.state, "agent") or app.state.agent is None:
        raise HTTPException(status_code=500, detail="L'agent RAG n'est pas initialisé.")

    try:
        system_prompt = SystemMessage(
            content="Tu es HorRAGor, une entité cybernétique cinéphile sarcastique et précise. "
            "Tu as accès à des outils. Pense étape par étape (ReAct).\n"
            "RÈGLE ABSOLUE : Si un outil te renvoie 'Aucun résultat' ou une erreur, "
            "TU NE DOIS SOUS AUCUN PRÉTEXTE inventer des films ou des informations. "
            "Avoue simplement que tes bases de données sont vides sur ce sujet."
        )
        inputs = {"messages": [system_prompt, HumanMessage(content=request.question)]}
        config = {"configurable": {"thread_id": request.user_id}}

        # ON LANCE LE GRAPH ! (L'agent réfléchit, utilise FAISS puis Supabase)
        result = app.state.agent.invoke(inputs, config)
        reponse_finale = result["messages"][-1].content

        return ChatResponse(
            answer=reponse_finale,
            sources=["LangGraph Agent", "FAISS Router", "Supabase PostgreSQL"],
            needs_ui_feedback=False,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
