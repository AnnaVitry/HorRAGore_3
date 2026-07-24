from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from src.models.state import AgentState, EvaluationVerdict
from src.tools.rag_tool import find_similar_horror_movies, query_movie_metadata


# --- SCHÉMA D'EXTRACTION (STRUCTURED OUTPUT) ---
class RagHarvest(BaseModel):
    """Schéma Pydantic pour forcer le LLM à structurer sa récolte de données."""

    local_lore: dict[str, Any] = Field(
        description="Faits locaux extraits (budget, date, réalisateur, etc.)"
    )
    is_database_sufficient: bool = Field(
        description="True si les infos suffisent, False si des détails manquent"
    )


# --- 1. INITIALISATION DES MODÈLES LLM ---
llm_tech = ChatOllama(model="llama3.1", temperature=0.1)
llm_creative = ChatOllama(model="llama3.1", temperature=0.3)
llm_judge = ChatOllama(model="llama3.1", temperature=0.0)

# --- 2. L'AGENT RAG (Fouille Locale) ---
rag_tools = [query_movie_metadata, find_similar_horror_movies]
rag_agent_llm = llm_tech.bind_tools(rag_tools)


def rag_node(state: AgentState) -> dict[str, Any]:
    """Premier agent : Cherche dans Supabase et extrait un état structuré."""
    messages = state["messages"]
    system_prompt = SystemMessage(
        content=(
            "Tu es un chercheur expert en bases de données d'horreur. "
            "Utilise les outils SQL et Vectoriels pour extraire les infos. "
            "Fournis uniquement le titre brut du film lors des appels d'outils."
        )
    )

    response = rag_agent_llm.invoke([system_prompt] + messages)

    if response.tool_calls:
        return {"messages": [response]}

    extractor = llm_tech.with_structured_output(RagHarvest)
    harvest_prompt = SystemMessage(
        content=(
            "Tu es l'Analyste des Archives de l'Horreur (RAG).\n"
            "Évalue si le contexte extrait de la base locale est SUFFISANT.\n"
            "La base contient UNIQUEMENT des métadonnées de surface (synopsis, réalisateur, date).\n"
            "Elle NE CONTIENT PAS d'informations sur les tournages ou les anecdotes.\n"
            "Si la question concerne le tournage -> `is_database_sufficient = False`."
        )
    )

    harvest = extractor.invoke([harvest_prompt] + messages)
    final_decision = harvest.is_database_sufficient

    # Garde-fou intelligent anti-hallucination de succès
    lore_text = str(harvest.local_lore).strip().lower()
    if final_decision is True:
        fail_words = [
            "désolé",
            "aucune donnée",
            "pas d'information",
            "aucun résultat",
            "none",
            "",
        ]
        if any(word in lore_text for word in fail_words):
            final_decision = False

    # Sécurité sémantique explicite
    last_user_message = next(
        (m.content.lower() for m in reversed(messages) if m.type == "human"), ""
    )
    if (
        "tournage" in last_user_message
        or "anecdote" in last_user_message
        or "secret" in last_user_message
    ):
        final_decision = False

    return {
        "messages": [response],
        "local_lore": harvest.local_lore,
        "is_database_sufficient": final_decision,
    }


# --- SCHÉMA D'EXTRACTION POUR LE TITRE ---
class MovieTitleExtraction(BaseModel):
    """Schéma strict pour forcer le LLM à isoler le titre du film."""

    title: str = Field(description="Le titre exact du film d'horreur mentionné.")


# --- 3. L'AGENT SCRAPER (Enquêteur Web) ---
def scraper_node(state: AgentState) -> dict[str, Any]:
    """Agent Scraper isolé : Isole le titre et appelle l'outil Wikipédia."""
    messages = state["messages"]

    extractor = llm_tech.with_structured_output(MovieTitleExtraction)
    extraction_prompt = SystemMessage(
        content="Analyse la conversation et isole uniquement le titre du film."
    )

    try:
        title_data = extractor.invoke([extraction_prompt] + messages)
        movie_title = title_data.title
    except Exception:
        user_question = [m.content for m in messages if m.type == "human"][-1]
        movie_title = user_question

    print(f"🎯 [SCRAPER NODE] Titre extrait pour Wikipédia : {movie_title}")

    try:
        from src.tools.scrapper_tool import scrape_detailed_synopsis

        web_result = scrape_detailed_synopsis.invoke({"movie_title": movie_title})
        print(f"\n🕸️ [DEBUG WEB] Résultat brut : {web_result[:300]}...\n")
    except Exception as e:
        web_result = f"Échec de l'extraction web : {e}"

    return {"web_anecdotes": [web_result]}


# --- 4. L'AGENT NARRATION (L'Écrivain Gothique) ---
def narration_node(state: AgentState) -> dict[str, Any]:
    """Dernier agent : Répond à n'importe quelle requête horrifique avec style et concision."""
    messages = state["messages"]

    # 1. On récupère la vraie question posée par l'utilisateur
    user_question = next(
        (m.content for m in messages if m.type == "human"), "Question sur l'horreur"
    )

    # 2. On rassemble toutes les sources disponibles (Supabase + Web)
    local_lore = state.get("local_lore", {})
    web_data = state.get("web_anecdotes", [])

    system_prompt = SystemMessage(
        content=(
            "Tu es HorRAGor, une entité cynique d'une élégance froide, Oracle suprême de l'horreur.\n\n"
            f'QUESTION DE L\'UTILISATEUR : "{user_question}"\n\n'
            f"DONNÉES LOCALES (Supabase) : {local_lore}\n"
            f"DONNÉES WEB (Wikipédia) : {web_data}\n\n"
            "RÈGLES DE RÉDACTION :\n"
            "1. Réponds précisément à ce qui est demandé (qu'il s'agisse d'un calcul de survie, du nombre de films, d'un casting ou de détails de tournage).\n"
            "2. Sois percutant et direct : **1 à 2 paragraphes maximum** (interdiction absolue de faire une dissertation de 10 lignes).\n"
            "3. Conserve ton ton sarcastique, sombre et hautain, fidèle à ton personnage."
        )
    )

    sterile_command = HumanMessage(
        content="Génère ta réponse cynique en exploitant les données fournies et en restant concis."
    )

    response = llm_creative.invoke([system_prompt, sterile_command])
    return {"messages": [response]}


# --- 5. CONTRÔLE QUALITÉ (Le Juge) ---
def quality_control_node(state: AgentState) -> dict[str, Any]:
    """Évalue la réponse de l'Écrivain (Uniquement sur le ton et l'ambiance)."""
    messages = state["messages"]
    last_agent_message = messages[-1].content

    # L'appel au LLM reste sous format Pydantic pour garantir la structure
    evaluator_llm = llm_judge.with_structured_output(EvaluationVerdict)

    audit_prompt = SystemMessage(
        content=(
            "Tu es HorRAGor, l'Auditeur Suprême des Ténèbres.\n\n"
            "RÈGLE UNIQUE À VÉRIFIER :\n"
            "Le texte doit-il être rejeté ? Réponds 'NON' **uniquement** si le texte est plat, gentil, trop court, ou totalement horssujet.\n"
            "Si le texte a de l'ambiance, du cynisme, et parle du film, ton verdict DOIT être 'OUI'. Sois indulgent.\n\n"
            f'TEXTE À AUDITER : "{last_agent_message}"\n\n'
            "Rédige une brève analyse et donne ton verdict (OUI ou NON)."
        )
    )
    # 1. Le LLM renvoie l'objet Pydantic
    verdict_obj = evaluator_llm.invoke([audit_prompt])
    print(
        f"\n⚖️ [JUGE] Analyse : {verdict_obj.analyse_preliminaire}\nVerdict : {verdict_obj.grade} | Critique : {verdict_obj.critique}\n"
    )

    # 2. CONVERSION EN DICTIONNAIRE pour la sauvegarde LangGraph
    verdict_dict = verdict_obj.model_dump()

    if verdict_obj.grade == "NON":
        correction_message = HumanMessage(
            content=f"REFUSÉ. Motif : {verdict_obj.critique}. Mets plus de cynisme et de noirceur."
        )
        # On passe le dictionnaire à LangGraph
        return {"verdict": verdict_dict, "messages": [correction_message]}

    # On passe le dictionnaire à LangGraph
    return {"verdict": verdict_dict}


tools_node = ToolNode(rag_tools)
