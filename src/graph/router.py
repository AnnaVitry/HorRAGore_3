from langchain_core.messages import AIMessage

from src.models.state import AgentState


def route_after_rag(state: AgentState) -> str:
    """Aiguille le flux après l'agent RAG (Outils, Scraper ou Narration)."""
    last_message = state["messages"][-1]

    # 1. Priorité absolue : l'agent a-t-il besoin d'utiliser un outil ?
    if getattr(last_message, "tool_calls", None):
        return "tools"

    # 2. Sinon, on lit le flag décisionnel rempli par le Structured Output
    is_sufficient = state.get("is_database_sufficient", True)

    if is_sufficient:
        print("🔮 [ROUTEUR] : Savoir local suffisant. Vers la Narration.")
        return "narration_agent"

    print("🕷️ [ROUTEUR] : Savoir incomplet. Déviation vers le Scraper.")
    return "scraper_agent"


def route_after_scraper(state: AgentState) -> str:
    """Aiguille le flux après l'agent Scraper (Outils ou Narration)."""
    last_message = state["messages"][-1]

    if getattr(last_message, "tool_calls", None):
        return "tools"

    return "narration_agent"


def route_after_tools(state: AgentState) -> str:
    """Retourne le flux à l'agent ayant invoqué l'outil."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            tool_name = msg.tool_calls[0]["name"]
            # Si c'était l'outil Wikipédia, on retourne au Scraper
            if tool_name == "scrape_detailed_synopsis":
                return "scraper_agent"
            # Sinon, c'était un outil du RAG, on retourne au RAG
            return "rag_agent"

    return "rag_agent"
