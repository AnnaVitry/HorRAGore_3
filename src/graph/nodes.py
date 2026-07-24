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

# On passe sur un modèle plus puissant (8B) pour garantir la logique de l'extraction.
llm_tech = ChatOllama(model="llama3.1", temperature=0.1)
llm_creative = ChatOllama(model="llama3.1", temperature=0.3)
# Initialisation du Juge (Température 0 pour l'analyse stricte)
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

    # Si le LLM décide d'utiliser un outil, on s'arrête là pour ce cycle
    if response.tool_calls:
        return {"messages": [response]}

    # Extraction structurée pour isoler le contexte (Context Trimming)
    extractor = llm_tech.with_structured_output(RagHarvest)
    harvest_prompt = SystemMessage(
        content=(
            "Analyse l'historique et extrais les métadonnées de la base locale. "
            "Évalue si les données suffisent."
        )
    )

    harvest = extractor.invoke([harvest_prompt] + messages)

    # --- LE COUPE-CIRCUIT (GUARDRAIL) ---
    # On récupère la dernière question de l'utilisateur
    last_user_message = next(
        (m.content.lower() for m in reversed(messages) if m.type == "human"), ""
    )

    # Mots déclencheurs qui forcent l'appel au web, peu importe ce que pense le LLM
    trigger_words = ["anecdote", "secret", "tournage", "wiki", "détail"]

    # Remplacement autoritaire de la décision
    if any(word in last_user_message for word in trigger_words):
        print(
            "🛡️ [GUARDRAIL] Mot-clé détecté. Annulation de la décision de l'IA. Forçage vers le Scraper."
        )
        final_decision = False
    else:
        final_decision = harvest.is_database_sufficient

    return {
        "messages": [response],
        "local_lore": harvest.local_lore,
        "is_database_sufficient": final_decision,
    }


# --- SCHÉMA D'EXTRACTION POUR LE TITRE ---
class MovieTitleExtraction(BaseModel):
    """Schéma strict pour forcer le LLM à isoler le titre du film."""

    title: str = Field(
        description="Le titre exact du film d'horreur mentionné, corrigé si mal orthographié."
    )


# --- 3. L'AGENT SCRAPER (Enquêteur Web) ---
def scraper_node(state: AgentState) -> dict[str, Any]:
    """Agent Scraper : Exécution programmatique avec extraction structurée du titre."""
    messages = state["messages"]

    # 1. Extraction robuste via Pydantic
    extractor = llm_tech.with_structured_output(MovieTitleExtraction)
    extraction_prompt = SystemMessage(
        content="Analyse la conversation et isole le titre du film. Corrige l'orthographe si nécessaire."
    )

    try:
        # On force le LLM à répondre dans le format JSON de Pydantic
        title_data = extractor.invoke([extraction_prompt] + messages)
        movie_title = title_data.title
    except Exception:  # noqa: BLE001
        # Fallback de sécurité au cas où le LLM crashe
        user_question = [m.content for m in messages if m.type == "human"][-1]
        movie_title = user_question

    print(f"🎯 [SCRAPER] Titre extrait pour Wikipédia : {movie_title}")

    # 2. Appel Programmatique de l'outil
    try:
        from src.tools.scrapper_tool import scrape_detailed_synopsis

        web_result = scrape_detailed_synopsis.invoke({"movie_title": movie_title})
        print(f"\n🕸️ [DEBUG WEB] Résultat brut : {web_result[:400]}...\n")
    except Exception as e:  # noqa: BLE001
        web_result = f"Échec de l'extraction web : {e}"

    # 3. On injecte le résultat réel dans l'état
    return {"web_anecdotes": [web_result]}


# --- 4. L'AGENT NARRATION (L'Écrivain Gothique) ---
# --- 4. L'AGENT NARRATION (L'Écrivain Gothique) ---
def narration_node(state: AgentState) -> dict[str, Any]:
    """Dernier agent : Rédige la réponse finale isolée de la plomberie."""

    # La ligne contenant `messages = state["messages"]` a été supprimée.
    web_data = state.get("web_anecdotes", [])

    # On adoucit légèrement les termes ("cynique" au lieu de "macabre") pour éviter les blocages de sécurité de Llama 3.
    system_prompt = SystemMessage(
        content=(
            "Tu es HorRAGor, une entité cynique d'une élégance froide. "
            "TRADUIS et RÉSUME en français les faits de tournage suivants :\n\n"
            f"DONNÉES BRUTES : {web_data}\n\n"
            "RÈGLES :\n"
            "1. Ne parle QUE des lieux de tournage et des décors mentionnés ci-dessus.\n"
            "2. Rédige 3 phrases maximum, avec un ton sarcastique."
        )
    )

    # LE COUP DE MAÎTRE ARCHITECTURAL : On coupe le fil avec l'utilisateur.
    # On ne lui passe PAS la question brute (qui contient le titre du film et déclenche l'hallucination).
    # On la remplace par un ordre d'exécution stérile.
    sterile_command = HumanMessage(
        content="Génère ton récit cynique basé EXCLUSIVEMENT sur les données fournies, sans rien ajouter de ton propre savoir."
    )

    response = llm_creative.invoke([system_prompt, sterile_command])

    # On préserve l'historique de la conversation pour le graphe
    return {"messages": [response]}


def quality_control_node(state: AgentState) -> dict[str, Any]:
    """
    Évalue la réponse de l'Écrivain Gothique et audite le respect des consignes.

    Args:
        state (AgentState): L'état courant du graphe contenant l'historique.

    Returns:
        Dict[str, Any]: Le verdict Pydantic et l'injonction de correction si refusé.
    """
    messages = state["messages"]

    # On isole le texte fraîchement généré par l'Écrivain
    last_agent_message = messages[-1].content

    # Le Juge est contraint par Pydantic
    evaluator_llm = llm_judge.with_structured_output(EvaluationVerdict)

    audit_prompt = SystemMessage(
        content=(
            "Tu es un Auditeur Qualité intraitable. "
            "Examine le texte suivant généré par l'Écrivain Gothique.\n\n"
            "RÈGLES À AUDITER :\n"
            "1. LONGUEUR : Le texte DOIT faire 3 phrases STRICT MAXIMUM.\n"
            "2. TON : Le texte DOIT être cynique et sarcastique.\n"
            "3. FAITS : Aucun ajout d'éléments paranormaux imaginaires (pas de malédiction, etc.).\n\n"
            f'TEXTE À AUDITER : "{last_agent_message}"\n\n'
            "Rédige d'abord ton analyse préliminaire. Ensuite, si UNE SEULE règle est violée, ton verdict final DOIT être 'NON'."
        )
    )

    # Exécution de l'audit
    verdict = evaluator_llm.invoke([audit_prompt])
    print(
        f"\n⚖️ [JUGE] Analyse : {verdict.analyse_preliminaire}\nVerdict : {verdict.grade} | Critique : {verdict.critique}\n"
    )

    # Si refusé, on crée un message autoritaire pour obliger l'Écrivain à corriger sa copie
    if verdict.grade == "NON":
        correction_message = HumanMessage(
            content=f"REFUSÉ par le contrôle qualité. Motif : {verdict.critique}. Corrige ce défaut et génère une nouvelle version."
        )
        return {"verdict": verdict, "messages": [correction_message]}

    return {"verdict": verdict}


# --- 5. L'OUTIL DE ROUTAGE DES FONCTIONS ---
tools_node = ToolNode(rag_tools)
