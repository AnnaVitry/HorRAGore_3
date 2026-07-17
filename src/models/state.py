from typing import Annotated, Any, Dict, List

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """L'état de confiance (mémoire commune) partagé par tous les agents."""

    # Historique complet des messages (géré par le reducer add_messages)
    messages: Annotated[List[BaseMessage], add_messages]

    # Données structurées et sémantiques récupérées en local (FAISS / Supabase)
    local_lore: Dict[str, Any]

    # Anecdotes et faits bruts récupérés sur le Web par le scraper
    web_anecdotes: List[str]

    # Flag décisionnel levé par le nœud RAG pour guider le routeur
    is_database_sufficient: bool
