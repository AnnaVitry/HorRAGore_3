from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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

    # 3. Lancement du graphe (jusqu'au point de contrôle "tools")
    try:
        response = app_graph.invoke({"messages": messages_utilisateur}, config)
    except Exception as e:  # noqa: BLE001
        print(f"❌ Erreur lors de l'exécution du graphe : {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # 4. Vérification de l'état du graphe
    state_info = app_graph.get_state(config)

    if state_info.next:
        # Le graphe est suspendu
        last_message = state_info.values["messages"][-1]

        tool_name = "inconnu"
        tool_call_id = None
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            tool_name = last_message.tool_calls[0]["name"]
            tool_call_id = last_message.tool_calls[0]["id"]

        print(f"\n🛑 [HITL DÉCLENCHÉ] L'agent veut exécuter l'outil : {tool_name}")

        # 5. Validation Humaine (Terminal)
        user_decision = input("VALIDATION : Autoriser l'action ? (oui/non) : ")

        if user_decision.lower() == "oui":
            print("✅ Action autorisée. Reprise du graphe...")
            response = app_graph.invoke(None, config)
        else:
            print("❌ Action refusée. Injection du refus dans la mémoire de l'agent...")

            refusal_message = ToolMessage(
                content="Opération refusée par l'administrateur système pour des raisons de sécurité. Explique cela à l'utilisateur de manière cynique.",
                tool_call_id=tool_call_id,
                name=tool_name,
            )

            app_graph.update_state(
                config, {"messages": [refusal_message]}, as_node="tools"
            )
            # On relance le graphe qui lira ce refus et passera à la suite
            response = app_graph.invoke(None, config)

    # 6. Extraction sécurisée de la réponse finale
    # On filtre pour ne récupérer que les messages générés par le LLM (AIMessage)
    ai_messages = [m for m in response["messages"] if isinstance(m, AIMessage)]

    # On prend le dernier message de l'IA (ou le dernier message global si erreur)
    if ai_messages:
        final_message = ai_messages[-1].content
    else:
        final_message = response["messages"][-1].content

    return ChatResponse(answer=final_message, needs_ui_feedback=False)
