from langchain_core.messages import AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.prebuilt import ToolNode

from src.models.state import AgentState

# On importe les outils que tu as isolés
from src.tools.rag_tool import find_similar_horror_movies, query_movie_metadata
from src.tools.scrapper_tool import scrape_detailed_synopsis

# from src.tools.misc_tools import calculate_movie_age, horror_survival_simulator

# --- 1. INITIALISATION DES MODÈLES LLM ---
# On utilise une température basse (0.1) pour les agents techniques (ils doivent être précis)
llm_tech = ChatOllama(model="llama3.2:3b", temperature=0.1)
# On utilise une température plus haute (0.7) pour le narrateur (il doit être créatif)
llm_creative = ChatOllama(model="llama3.2:3b", temperature=0.7)

# --- 2. L'AGENT RAG (Fouille Locale) ---
# On lui attache UNIQUEMENT ses outils de base de données
rag_tools = [query_movie_metadata, find_similar_horror_movies, scrape_detailed_synopsis]
rag_agent_llm = llm_tech.bind_tools(rag_tools)


def rag_node(state: AgentState):
    """Premier agent de la chaîne : Cherche dans Supabase."""
    print("🦇 [Agent RAG] Analyse de la demande...")
    messages = state["messages"]

    system_prompt = SystemMessage(
        content="Tu es un chercheur expert en bases de données d'horreur. "
        "Ton unique rôle est d'utiliser les outils SQL et Vectoriels pour extraire "
        "les informations brutes (budget, date, réalisateur, films similaires). "
        "Ne fais pas de phrases compliquées, fournis juste les faits."
        """
        RÈGLE ABSOLUE POUR LES OUTILS : 
        Lorsque tu appelles 'query_movie_metadata' ou 'find_similar_horror_movies', 
        tu dois fournir UNIQUEMENT le titre brut du film, SANS JAMAIS ajouter la date de sortie.
        Exemple CORRECT : 'Alien' ou 'Psycho'
        Exemple INTERDIT : 'Alien (1979)' ou 'Psycho (1960)'
        """
    )

    # L'agent invoque le LLM avec ses outils attachés
    response = rag_agent_llm.invoke([system_prompt] + messages)

    # On renvoie le message, LangGraph l'ajoutera automatiquement au 'state' grâce à operator.add
    return {"messages": [response]}


# --- 3. L'AGENT SCRAPER (Enquêteur Web) ---
# On lui attache UNIQUEMENT l'outil Wikipédia
scraper_tools = [scrape_detailed_synopsis]
scraper_agent_llm = llm_tech.bind_tools(scraper_tools)


def scraper_node(state: AgentState):
    """Deuxième agent (Optionnel) : Cherche sur Wikipédia si besoin."""
    print("🕸️ [Agent Scraper] Fouille du web en cours...")
    messages = state["messages"]

    system_prompt = SystemMessage(
        content="Tu es un enquêteur du web. L'utilisateur ou l'Agent RAG a besoin de plus de détails. "
        "Utilise l'outil Wikipedia pour trouver des anecdotes ou un résumé détaillé du film."
    )

    response = scraper_agent_llm.invoke([system_prompt] + messages)
    return {"messages": [response]}


# --- 4. L'AGENT NARRATION (L'Écrivain Gothique) ---
def narration_node(state: AgentState):
    """Dernier agent : Rédige la réponse finale SANS avoir d'outils (Context Trimming)."""
    print("🧛‍⚧️ [Agent Narration] Rédaction de la réponse finale...")
    messages = state["messages"]

    # TECHNIQUE DEVIA 25 : Context Trimming
    # Au lieu de donner tout l'historique brut (qui contient des appels de fonctions JSON bizarres),
    # on extrait proprement uniquement le texte utile pour l'écrivain.
    informations_recoltees = ""
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.content:
            informations_recoltees += f"- {msg.content}\n"

    system_prompt = SystemMessage(
        content="Tu es HorRAGor, une entité cybernétique cinéphile sarcastique et terrifiante. "
        "Ta mission est de répondre à l'utilisateur de manière immersive, horrifique et détaillée. "
        "Tu DOIS utiliser les informations factuelles qui t'ont été transmises ci-dessous pour construire ton récit.\n\n"
        f"### INFORMATIONS FACTUELLES RÉCOLTÉES PAR LES AUTRES AGENTS :\n{informations_recoltees}"
        """
        RÈGLE DE FORMATAGE ABSOLUE :
        Tu es le narrateur final. Tu dois délivrer ton récit d'un seul bloc immersif. 
        Il t'est STRICTEMENT INTERDIT de montrer tes étapes de réflexion (ex: "Étape 1", "Recherche en cours..."). 
        N'utilise jamais de parenthèses pour décrire tes actions ou pensées internes. Reste dans ton personnage d'entité gothique et terrifiante du début à la fin.
        """
    )

    # On lui passe juste le prompt système (qui contient les infos) et la question originale de l'utilisateur
    question_utilisateur = messages[0]  # Le premier message est toujours celui du Human

    response = llm_creative.invoke([system_prompt, question_utilisateur])
    return {"messages": [response]}


# On rassemble tous les outils dans une liste globale pour le ToolNode de LangGraph
all_tools = rag_tools + scraper_tools

# Le ToolNode est une fonction native de LangGraph qui exécute l'outil demandé par un agent
tools_node = ToolNode(all_tools)
