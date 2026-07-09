from langgraph.graph import END, START, StateGraph

# Import des ouvriers
from src.graph.nodes import narration_node, rag_node, tools_node

# Import de l'aiguilleur
from src.graph.router import should_continue_rag
from src.models.state import AgentState

# 1. Initialisation du Graphe avec notre mémoire commune
workflow = StateGraph(AgentState)

# 2. Enregistrement des fonctions dans le moteur (Les Nœuds) [cite: 68]
workflow.add_node("rag_agent", rag_node)
workflow.add_node("tools", tools_node)
# workflow.add_node("scraper_agent", scraper_node) # Désactivé temporairement pour le test
workflow.add_node("narration_agent", narration_node)

# 3. Traçage des autoroutes (Edges) [cite: 69]
workflow.add_edge(START, "rag_agent")

# 4. Greffe des aiguilleurs (Conditional Edges) [cite: 70]
workflow.add_conditional_edges(
    "rag_agent", should_continue_rag, {"tools": "tools", "narration": "narration_agent"}
)

# Quand les outils ont fini de chercher en base, ils renvoient les données au RAG
workflow.add_edge("tools", "rag_agent")

# Quand la narration a fini de rédiger, le processus s'arrête
workflow.add_edge("narration_agent", END)

# 5. Compilation du système prêt à l'emploi [cite: 71, 72]
app_graph = workflow.compile()
