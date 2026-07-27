from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_ollama import ChatOllama
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from src.models.state import AgentState, EvaluationVerdict
from src.tools.rag_tool import find_similar_horror_movies, query_movie_metadata
from src.tools.scraper_tool import scrape_detailed_synopsis


# --- SCHÉMA D'EXTRACTION (STRUCTURED OUTPUT) ---
class RagHarvest(BaseModel):
    """Schéma Pydantic pour forcer le LLM à structurer sa récolte de données."""

    local_lore: dict[str, Any] = Field(
        description="Faits locaux extraits (budget, date, réalisateur, etc.)"
    )
    # Chain-of-Thought : ce champ est rempli AVANT le booléen, donc le modèle est
    # contraint de raisonner sur la couverture réelle avant de trancher.
    couverture_analyse: str = Field(
        description=(
            "Raisonnement OBLIGATOIRE. Décris ce que demande précisément l'utilisateur, "
            "puis confronte chaque aspect de la demande aux métadonnées réellement extraites. "
            "Rappel : la base ne contient QUE des données de surface (synopsis, réalisateur, "
            "date, budget, note) et JAMAIS d'anecdotes de tournage, de production ou de "
            "coulisses. Conclus en listant ce qui est couvert et ce qui manque."
        )
    )
    is_database_sufficient: bool = Field(
        description=(
            "Verdict final déduit STRICTEMENT de 'couverture_analyse'. Mets False dès qu'un "
            "seul aspect de la question n'est pas couvert par les métadonnées de surface "
            "(ex : toute demande sur le tournage, les coulisses, la conception, les anecdotes)."
        )
    )


# --- 1. INITIALISATION DES MODÈLES LLM ---
llm_tech = ChatOllama(model="llama3.1", temperature=0.1)
llm_creative = ChatOllama(model="llama3.1", temperature=0.3)
llm_judge = ChatOllama(model="llama3.1", temperature=0.0)

# --- 2. L'AGENT RAG (Fouille Locale) ---
rag_tools = [query_movie_metadata, find_similar_horror_movies]
rag_agent_llm = llm_tech.bind_tools(rag_tools)


def _lore_looks_empty(local_lore: Any) -> bool:
    """Détecte un 'lore' local vide ou négatif (garde-fou anti-hallucination de succès).

    Fonction PURE -> testable unitairement, dans l'esprit du spec sur router.py.
    NB : l'ancienne implémentation incluait "" dans la liste de mots, ce qui rendait
    la détection TOUJOURS vraie ('' est sous-chaîne de tout) et cassait la branche locale.
    """
    if not local_lore:
        return True
    lore_text = str(local_lore).strip().lower()
    negatifs = [
        "désolé",
        "aucune donnée",
        "pas d'information",
        "aucun résultat",
        "none",
    ]
    return any(mot in lore_text for mot in negatifs)


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
            "PROCÈDE EN DEUX TEMPS, dans cet ordre strict :\n"
            "1. Remplis d'abord 'couverture_analyse' : raisonne explicitement sur ce que\n"
            "   demande l'utilisateur et sur ce que les métadonnées extraites couvrent RÉELLEMENT.\n"
            "2. SEULEMENT ENSUITE, déduis 'is_database_sufficient' de ce raisonnement.\n\n"
            "RÈGLE ABSOLUE : la base contient UNIQUEMENT des métadonnées de surface\n"
            "(synopsis, réalisateur, date, budget, note). Elle NE CONTIENT JAMAIS d'informations\n"
            "sur le tournage, la production, la conception ou les anecdotes de coulisses.\n"
            "Donc toute demande portant sur ces aspects -> is_database_sufficient = False,\n"
            "quelle que soit la formulation (coulisses, making-of, fun fact, comment c'est fait...)."
        )
    )

    harvest = extractor.invoke([harvest_prompt] + messages)
    final_decision = harvest.is_database_sufficient

    # Trace du raisonnement CoT (précieux dans Langfuse pour auditer la décision)
    print(f"🧠 [RAG/CoT] Analyse couverture : {harvest.couverture_analyse}")
    print(f"🧭 [RAG] Base locale suffisante ? -> {final_decision}")

    # Garde-fou anti-hallucination de succès : si le "lore" est en réalité vide ou
    # négatif, on refuse la sortie locale même si le LLM s'est déclaré satisfait.
    # (Indépendant du CoT : protège contre une base vide.)
    if final_decision is True and _lore_looks_empty(harvest.local_lore):
        print("🛡️ [RAG] Lore local vide/négatif : bascule forcée vers le Scraper.")
        final_decision = False

    # NOTE : l'ancienne liste de mots-clés en dur (tournage/anecdote/secret) sur le
    # message utilisateur a été retirée. La décision repose désormais sur le raisonnement
    # CoT ci-dessus, robuste aux reformulations (coulisses, making-of, fun fact...).

    return {
        "messages": [response],
        "local_lore": harvest.local_lore,
        "is_database_sufficient": final_decision,
    }


# --- 3. L'AGENT SCRAPER (Enquêteur Web, désormais agentique) ---
scraper_tools = [scrape_detailed_synopsis]
scraper_agent_llm = llm_tech.bind_tools(scraper_tools)


def scraper_node(state: AgentState) -> dict[str, Any]:
    """Agent Scraper agentique : réclame l'outil Wikipédia au moteur, puis récolte le butin.

    Deux passages possibles :
    - 1er passage : le LLM émet un tool_call `scrape_detailed_synopsis` (routé vers `tools`).
    - 2e passage : le résultat de l'outil est déjà là -> on le range dans `web_anecdotes`
      (isolation du contexte) et on renvoie un message SANS tool_call pour filer vers la Narration.
    """
    messages = state["messages"]
    last = messages[-1]

    # --- 2e passage : on récolte le résultat de l'outil dans le State ---
    if (
        isinstance(last, ToolMessage)
        and getattr(last, "name", "") == "scrape_detailed_synopsis"
    ):
        web_result = last.content
        print(f"🕸️ [SCRAPER] Butin web récolté ({len(str(web_result))} car.).")
        transition = AIMessage(
            content="Enquête web terminée. Dossier transmis à la plume de la Narration."
        )
        return {"messages": [transition], "web_anecdotes": [web_result]}

    # --- 1er passage : on laisse le LLM décider d'appeler l'outil ---
    system_prompt = SystemMessage(
        content=(
            "Tu es l'Enquêteur Web de l'horreur. La base locale s'est révélée INSUFFISANTE.\n"
            "Ta mission : appeler l'outil `scrape_detailed_synopsis` pour extraire de Wikipédia "
            "les anecdotes de tournage/production manquantes.\n"
            "Passe UNIQUEMENT le titre brut du film comme argument `movie_title`."
        )
    )
    response = scraper_agent_llm.invoke([system_prompt] + messages)
    return {"messages": [response]}


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

    # 3. Si le Juge a rejeté la version précédente, on récupère SA critique
    #    (uniquement la chaîne de texte, pour préserver l'isolation du contexte :
    #     l'Écrivain ne voit jamais l'historique technique, seulement le motif du refus).
    verdict = state.get("verdict")
    correction = ""
    if verdict and verdict.get("grade") == "NON":
        motif = verdict.get("critique", "").strip() or "Texte jugé trop plat."
        correction = (
            "\n\n⚠️ RÉÉCRITURE IMPOSÉE PAR L'AUDITEUR DES TÉNÈBRES.\n"
            f"Ta version précédente a été REJETÉE pour ce motif précis : « {motif} ».\n"
            "Corrige EXACTEMENT ce défaut : intensifie le cynisme et la noirceur, "
            "sans inventer de nouveaux faits ni dépasser 2 paragraphes."
        )

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
            f"{correction}"
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


# Le ToolNode connaît désormais AUSSI l'outil du Scraper.
# Le routage de retour (rag_agent vs scraper_agent) est géré par route_after_tools.
tools_node = ToolNode(rag_tools + scraper_tools)
