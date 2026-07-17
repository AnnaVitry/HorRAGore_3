from langgraph.graph import END, START, StateGraph

# Import des ouvriers (Nodes)
from src.graph.nodes import narration_node, rag_node, scraper_node, tools_node

# Import de notre mémoire commune
from src.models.state import AgentState

# 1. Initialisation du Graphe avec notre mémoire commune
workflow = StateGraph(AgentState)

# 2. Enregistrement des fonctions dans le moteur (Les Nœuds)
workflow.add_node("rag_agent", rag_node)
workflow.add_node("tools", tools_node)
workflow.add_node("scraper_agent", scraper_node)  # 🔥 Réactivé pour la Partie 3 !
workflow.add_node("narration_agent", narration_node)

# --- FARA : LOGIQUES DE ROUTAGE AVANCÉES (AIGUILLAGE) ---


def should_continue_rag(state: AgentState) -> str:
    """Analyse les messages après le RAG : boucle sur les outils OU passe à la suite."""
    messages = state["messages"]
    last_message = messages[-1]

    # A. Si le LLM du RAG veut appeler un outil (SQL ou Recommandation Vectorielle)
    if last_message.tool_calls:
        return "tools"

    # B. Si pas d'outil, la fouille locale est finie. On checke s'il faut aller sur le web.
    user_messages = [m for m in messages if m.type == "human"]
    user_question = user_messages[-1].content.lower()
    need_keywords = [
        "anecdote",
        "tournage",
        "wikipedia",
        "wiki",
        "secret",
        "histoire",
        "coulisse",
    ]
    user_wants_anecdote = any(kw in user_question for kw in need_keywords)

    # Si l'utilisateur veut une anecdote ou si la base a répondu qu'elle n'avait rien
    rag_text = last_message.content.lower() if last_message.content else ""
    database_empty = "aucune métadonnée" in rag_text or "introuvable" in rag_text

    if user_wants_anecdote or database_empty:
        return "scraper_agent"

    return "narration_agent"


def should_continue_scraper(state: AgentState) -> str:
    """Analyse les messages après le Scraper : boucle sur les outils OU passe à l'écriture."""
    last_message = state["messages"][-1]

    # Si l'agent Scraper appelle son outil Wikipédia
    if last_message.tool_calls:
        return "tools"

    return "narration_agent"


def router_after_tools(state: AgentState) -> str:
    """Aiguilleur intelligent : renvoie le flux à l'agent qui a appelé l'outil."""
    # On inspecte les messages à l'envers pour trouver l'initiateur du ToolCall
    for msg in reversed(state["messages"]):
        if msg.type == "ai" and msg.tool_calls:
            tool_name = msg.tool_calls[0]["name"]
            # Si c'était l'outil Wikipédia, on retourne au Scraper
            if tool_name == "scrape_detailed_synopsis":
                return "scraper_agent"
            # Sinon, c'était un outil du RAG (SQL/PGVector), on retourne au RAG
            return "rag_agent"
    return "rag_agent"


# 3. Traçage des autoroutes (Edges)
workflow.add_edge(START, "rag_agent")

# 4. Greffe des aiguilleurs conditionnels
workflow.add_conditional_edges(
    "rag_agent",
    should_continue_rag,
    {
        "tools": "tools",
        "scraper_agent": "scraper_agent",
        "narration_agent": "narration_agent",
    },
)

workflow.add_conditional_edges(
    "scraper_agent",
    should_continue_scraper,
    {"tools": "tools", "narration_agent": "narration_agent"},
)

# Gestion du retour dynamique du ToolNode vers le bon ouvrier
workflow.add_conditional_edges(
    "tools",
    router_after_tools,
    {"rag_agent": "rag_agent", "scraper_agent": "scraper_agent"},
)

# Quand la narration a fini de rédiger, le processus s'arrête
workflow.add_edge("narration_agent", END)

# 5. Compilation du système prêt à l'emploi
app_graph = workflow.compile()
