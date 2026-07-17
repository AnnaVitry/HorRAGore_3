from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler

# Import du graphe Multi-Agent compilé
from src.graph.pipeline import app_graph

# Contrats de modèles (Pydantic)
from src.models.chat_models import ChatRequest, ChatResponse

# Connexion DB pour le check de santé
from src.tools.rag_tool import SessionLocal
from supabase_db import Media


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'API.
    S'exécute au démarrage du serveur.
    """
    print("🚀 Démarrage du système Multi-Agent HorRAGor...")

    # 1. Vérification rapide de la connexion Supabase
    try:
        db = SessionLocal()
        db.query(Media).first()
        db.close()
        print("✅ Connexion BDD Supabase opérationnelle.")
    except Exception as e:
        print(f"❌ Erreur critique DB : {e}")

    # 2. Injection du graphe compilé dans l'état de l'application
    # Le chargement de l'index FAISS est géré automatiquement
    # par le singleton dans rag_tool.py lors de l'import.
    app.state.agent = app_graph

    yield
    print("🛑 Arrêt du serveur.")


app = FastAPI(
    title="HorRAGor v3.0 API",
    description="Architecture distribuée Multi-Agent sous LangGraph",
    version="3.0",
    lifespan=lifespan,
)


@app.get("/")
async def health_check():
    """Vérification de survie du système."""
    return {"status": "HorRAGor 3.0 est réveillé et prêt."}


# Instancie le handler (il lira automatiquement tes variables d'environnement)
langfuse_handler = CallbackHandler()


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint principal pour dialoguer avec les agents.
    Le routage entre RAG, Scraper et Narration est géré par le graphe compilé.
    """
    try:
        inputs = {"messages": [HumanMessage(content=request.question)]}
        config = {
            "configurable": {"thread_id": request.user_id},
            "callbacks": [langfuse_handler],  # 👈 C'est ici que la magie opère
        }

        result = await app.state.agent.ainvoke(inputs, config=config)

        # Le dernier message est obligatoirement la prose finale de la Narration
        final_answer = result["messages"][-1].content

        return ChatResponse(
            answer=final_answer,
            sources=["Multi-Agent Flow"],
            needs_ui_feedback=False,
        )
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du graphe : {e}")
        raise HTTPException(status_code=500, detail=str(e))
