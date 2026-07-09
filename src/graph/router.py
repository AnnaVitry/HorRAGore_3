from src.models.state import AgentState


def should_continue_rag(state: AgentState):
    """
    Examine l'état après le passage de l'Agent RAG.
    """
    last_message = state["messages"][-1]

    # 1. Si le RAG demande à utiliser la base de données (SQL ou PGVector)
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # 2. (Simplification) Une fois que le RAG a fini, on passe le relais à l'écrivain.
    # Dans une version plus avancée, on pourrait vérifier ici si on doit dérouter vers le 'scraper'[cite: 60].
    return "narration"
