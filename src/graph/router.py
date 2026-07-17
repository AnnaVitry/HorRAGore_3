from src.models.state import AgentState


def should_scrape_or_narrate(state: AgentState) -> str:
    """Examine l'état actuel et décide d'aiguiller vers le Scraper ou la Narration."""

    # On extrait le flag décisionnel écrit par le nœud RAG
    is_sufficient = state.get("is_database_sufficient", True)

    # Règle d'or LangGraph : On renvoie le nom exact de la prochaine destination
    if is_sufficient:
        print(
            "🔮 [ROUTEUR] : Savoir local suffisant. Aiguillage direct vers l'Écrivain Gothique."
        )
        return "narration"

    print(
        "🕷️ [ROUTEUR] : Savoir local incomplet. Déviation du flux vers l'Enquêteur Web (Scraper)."
    )
    return "scraper"
