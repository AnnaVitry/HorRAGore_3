import operator
from collections.abc import Sequence
from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# --- SCHÉMA DU JUGE ---
class EvaluationVerdict(BaseModel):
    analyse_preliminaire: str = Field(
        description="Analyse étape par étape du texte pour vérifier la longueur, le ton et les faits. (Fais-le en premier)."
    )
    critique: str = Field(
        description="Résumé de la faute si une règle est violée. Laisse vide si tout est parfait."
    )
    # Le grade DOIT être à la fin pour que le LLM lise sa propre analyse avant de trancher.
    grade: Literal["OUI", "NON"] = Field(
        description="Verdict final. OUI si 100% conforme, NON si la moindre faille est détectée."
    )


# --- ÉTAT GLOBAL ---
class AgentState(TypedDict):
    """L'état de confiance (mémoire commune) partagé par tous les agents."""

    # L'opérateur add permet d'accumuler les messages (historique)
    # Historique complet des messages (géré par le reducer add_messages)
    messages: Annotated[Sequence[BaseMessage], operator.add]
    # Données structurées et sémantiques récupérées en local (FAISS / Supabase)
    local_lore: dict[str, Any]
    # Flag décisionnel levé par le nœud RAG pour guider le routeur
    is_database_sufficient: bool
    # Anecdotes et faits bruts récupérés sur le Web par le scraper
    web_anecdotes: list
    # La nouvelle variable transportant la décision du juge
    verdict: dict | None
