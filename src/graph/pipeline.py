"""Module de configuration et de compilation du graphe Multi-Agent HorRAGor.

Ce module utilise LangGraph pour assembler les différents nœuds (les agents)
et les arêtes conditionnelles (les routeurs) définis dans l'architecture.
Il constitue le point d'entrée central du moteur décisionnel.
"""

from langgraph.graph import END, START, StateGraph

# 2. Import des ouvriers (Logique métier)
from src.graph.nodes import (
    narration_node,
    rag_node,
    scraper_node,
    tools_node,
)

# 3. Import des aiguilleurs (Logique décisionnelle)
from src.graph.router import (
    route_after_rag,
    route_after_scraper,
    route_after_tools,
)

# 1. Import de la mémoire commune
from src.models.state import AgentState

print("⚙️ [PIPELINE] Assemblage du moteur Multi-Agent...")

# --- INITIALISATION DU GRAPHE ---
workflow = StateGraph(AgentState)

# --- ENREGISTREMENT DES NŒUDS (Les Ouvriers) ---
workflow.add_node("rag_agent", rag_node)
workflow.add_node("scraper_agent", scraper_node)
workflow.add_node("narration_agent", narration_node)
workflow.add_node("tools", tools_node)

# --- TRAÇAGE DES AUTOROUTES ET AIGUILLAGES ---

# Le point d'entrée est toujours l'agent RAG
workflow.add_edge(START, "rag_agent")

# Après le RAG, l'aiguilleur décide de la suite (Outils, Scraper, ou Narration)
workflow.add_conditional_edges(
    "rag_agent",
    route_after_rag,
    {
        "tools": "tools",
        "scraper_agent": "scraper_agent",
        "narration_agent": "narration_agent",
    },
)

# Après le Scraper, l'aiguilleur décide de la suite (Outils ou Narration)
workflow.add_conditional_edges(
    "scraper_agent",
    route_after_scraper,
    {
        "tools": "tools",
        "narration_agent": "narration_agent",
    },
)

# Après l'exécution d'un outil, on retourne le flux à son expéditeur
workflow.add_conditional_edges(
    "tools",
    route_after_tools,
    {
        "rag_agent": "rag_agent",
        "scraper_agent": "scraper_agent",
    },
)

# La Narration a toujours le mot de la fin
workflow.add_edge("narration_agent", END)

# --- COMPILATION ---
app_graph = workflow.compile()
print("✅ [PIPELINE] Système Multi-Agent compilé et prêt.")
