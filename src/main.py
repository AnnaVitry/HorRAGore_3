import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from langchain_core.messages import AIMessage, HumanMessage
from langfuse.langchain import CallbackHandler
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

# Import du graphe Multi-Agent compilé
from src.graph.pipeline import app_graph

# Contrats de modèles (Pydantic)
from src.models.chat_models import ChatRequest, ChatResponse

# Connexion DB pour le check de santé
from src.tools.rag_tool import SessionLocal
from supabase_db import Media

# ==============================================================================
# MÉTRIQUES PROMETHEUS
# Exposées sur GET /metrics — scrapées par Prometheus toutes les 15s
# ==============================================================================

# Nombre total de requêtes reçues par endpoint et statut HTTP
REQUEST_COUNT = Counter(
    "horragor_http_requests_total",
    "Nombre total de requêtes HTTP reçues",
    ["method", "endpoint", "status_code"],
)

# Latence des requêtes (histogram avec buckets adaptés à un LLM local ~2-10s)
REQUEST_LATENCY = Histogram(
    "horragor_http_request_duration_seconds",
    "Latence des requêtes HTTP en secondes",
    ["endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
)

# Nombre d'erreurs du graphe LangGraph
GRAPH_ERRORS = Counter(
    "horragor_graph_errors_total",
    "Nombre d'erreurs lors de l'exécution du graphe LangGraph",
)

# Nombre de requêtes chat traitées avec succès
CHAT_SUCCESS = Counter(
    "horragor_chat_success_total",
    "Nombre de réponses chat générées avec succès",
)


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
    except Exception as e:  # noqa: BLE001
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


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """Mesure la latence et compte chaque requête HTTP pour Prometheus."""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    endpoint = request.url.path
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

    return response


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Endpoint Prometheus — exposé sur /metrics, scrapé toutes les 15s."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    # 1. Extraction du message
    messages_utilisateur = [HumanMessage(content=request.question)]

    # 2. Configuration de la session dynamique et injection du monitoring Langfuse
    config = {
        "configurable": {"thread_id": request.user_id},
        "callbacks": [langfuse_handler],
    }

    # 3. Lancement du graphe en mode autonome (jusqu'à END, sans interruption humaine)
    try:
        response = app_graph.invoke({"messages": messages_utilisateur}, config)
    except Exception as e:  # noqa: BLE001
        print(f"❌ Erreur lors de l'exécution du graphe : {e}")
        GRAPH_ERRORS.inc()
        raise HTTPException(status_code=500, detail=str(e))

    # 4. Extraction sécurisée de la réponse finale
    # On filtre pour ne récupérer que les messages générés par le LLM (AIMessage)
    ai_messages = [m for m in response["messages"] if isinstance(m, AIMessage)]

    # On prend le dernier message de l'IA (ou le dernier message global si erreur)
    if ai_messages:
        final_message = ai_messages[-1].content
    else:
        final_message = response["messages"][-1].content

    CHAT_SUCCESS.inc()
    return ChatResponse(answer=final_message, needs_ui_feedback=False)
