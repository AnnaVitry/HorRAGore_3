import re
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
        description="Faits locaux extraits (titre, date, budget, note, univers, synopsis)."
    )
    # Chain-of-Thought : ce champ est rempli AVANT le booléen, donc le modèle est
    # contraint de raisonner sur la couverture réelle avant de trancher.
    couverture_analyse: str = Field(
        description=(
            "Raisonnement OBLIGATOIRE. Décris ce que demande précisément l'utilisateur, "
            "puis confronte chaque aspect de la demande aux métadonnées réellement extraites. "
            "Rappel : la base locale ne contient QUE des données de surface (titre, synopsis, "
            "date, budget, note, univers). Elle NE CONTIENT AUCUNE donnée de réalisateur, de "
            "casting, ni d'anecdotes de tournage, de production ou de coulisses. "
            "Conclus en listant ce qui est couvert et ce qui manque."
        )
    )
    is_database_sufficient: bool = Field(
        description=(
            "Verdict final déduit STRICTEMENT de 'couverture_analyse'. Mets False dès qu'un "
            "seul aspect de la question n'est pas couvert par les métadonnées de surface "
            "(ex : toute demande sur le réalisateur, le casting, le tournage, les coulisses, "
            "la conception ou les anecdotes)."
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
            "RÈGLE ABSOLUE : la base locale contient UNIQUEMENT des métadonnées de surface\n"
            "(titre, synopsis, date, budget, note, univers). Elle NE CONTIENT AUCUNE donnée\n"
            "de réalisateur, AUCUN casting, et JAMAIS d'informations sur le tournage, la\n"
            "production, la conception ou les coulisses.\n"
            "Donc toute demande portant sur le réalisateur, le casting ou ces aspects\n"
            "-> is_database_sufficient = False (elle devra passer par le scraper web),\n"
            "quelle que soit la formulation (réalisateur, acteurs, coulisses, making-of...)."
        )
    )

    harvest = extractor.invoke([harvest_prompt] + messages)
    final_decision = harvest.is_database_sufficient

    # Trace du raisonnement CoT (précieux dans Langfuse pour auditer la décision)
    print(f"🧠 [RAG/CoT] Analyse couverture : {harvest.couverture_analyse}")
    print(f"🧭 [RAG] Base locale suffisante ? -> {final_decision}")

    # --- VÉRITÉ-TERRAIN : on transmet les sorties BRUTES des outils (SQL / vectoriel), ---
    # jamais la ré-extraction du LLM. L'extracteur (RagHarvest) déformait la donnée
    # (ex : date 1979 -> 2024) ; on ne lui garde QUE la décision de routage
    # (is_database_sufficient + CoT), et les FAITS viennent directement du SQL brut.
    raw_tool_outputs = [str(m.content) for m in messages if isinstance(m, ToolMessage)]
    local_facts = "\n".join(raw_tool_outputs)

    # Garde-fou anti-hallucination de succès : si les faits bruts sont vides ou
    # négatifs, on refuse la sortie locale même si le LLM s'est déclaré satisfait.
    if final_decision is True and _lore_looks_empty(local_facts):
        print("🛡️ [RAG] Faits locaux vides/négatifs : bascule forcée vers le Scraper.")
        final_decision = False

    return {
        "messages": [response],
        # local_lore = données SQL BRUTES (source de vérité pour la Narration ET le Juge).
        "local_lore": {"faits_sql_bruts": local_facts},
        "is_database_sufficient": final_decision,
    }


# --- 3. L'AGENT SCRAPER (Enquêteur Web, désormais agentique) ---
scraper_tools = [scrape_detailed_synopsis]
scraper_agent_llm = llm_tech.bind_tools(scraper_tools)


def _extract_title_from_facts(facts: str) -> str | None:
    """Extrait le titre résolu depuis la sortie SQL brute ('Titre Exact: X, ...').

    Sert au fallback déterministe du scraper : on force l'appel Wikipédia avec CE
    titre exact, sans dépendre du bon vouloir du 8B pour émettre le tool_call.
    """
    match = re.search(r"Titre Exact:\s*(.+?)\s*,", facts)
    return match.group(1).strip() if match else None


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
        print(
            f"📄 [SCRAPER] Contenu brut (500 premiers car.) :\n{str(web_result)[:500]}\n"
        )
        transition = AIMessage(
            content="Enquête web terminée. Dossier transmis à la plume de la Narration."
        )
        return {"messages": [transition], "web_anecdotes": [web_result]}

    # --- 1er passage : on laisse le LLM décider d'appeler l'outil ---
    system_prompt = SystemMessage(
        content=(
            "Tu es l'Enquêteur Web de l'horreur. La base locale s'est révélée INSUFFISANTE.\n"
            "Ta mission : appeler l'outil `scrape_detailed_synopsis` pour extraire de Wikipédia "
            "les informations absentes du local — réalisateur, casting, anecdotes de "
            "tournage et de production.\n"
            "Passe UNIQUEMENT le titre brut du film comme argument `movie_title`."
        )
    )
    response = scraper_agent_llm.invoke([system_prompt] + messages)

    # Fallback DÉTERMINISTE : si le 8B n'a pas déclenché l'outil, on le force nous-mêmes
    # (sinon le scraper devient un no-op et web_anecdotes reste désespérément vide).
    if not getattr(response, "tool_calls", None):
        title = _extract_title_from_facts(str(state.get("local_lore", {})))
        if title:
            print(
                f"🔧 [SCRAPER] tool_call non émis par le LLM -> appel forcé pour « {title} »."
            )
            response.tool_calls = [
                {
                    "name": "scrape_detailed_synopsis",
                    "args": {"movie_title": title},
                    "id": "forced_scrape_1",
                    "type": "tool_call",
                }
            ]
        else:
            print("⚠️ [SCRAPER] Aucun titre résolu : impossible de forcer le scraping.")

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

    # Formatage explicite en texte lisible pour le LLM.
    # Sans ça, le f-string affiche ['...'] avec crochets/guillemets Python
    # et le 8B rate le contenu (d'où « archives muettes » malgré Ridley Scott présent).
    local_text = (
        local_lore.get("faits_sql_bruts", "Aucune donnée locale.")
        if isinstance(local_lore, dict)
        else str(local_lore)
    )
    web_text = (
        "\n\n---\n\n".join(str(w) for w in web_data)
        if web_data
        else "Aucune donnée web disponible."
    )

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
            "Corrige EXACTEMENT ce défaut. Si le motif est factuel (année, date, "
            "chiffre), utilise STRICTEMENT la valeur des données ci-dessus, sans en "
            "inventer d'autre. N'ajoute aucun fait absent des données et ne dépasse "
            "pas 2 paragraphes."
        )

    system_prompt = SystemMessage(
        content=(
            "Tu es HorRAGor, une entité cynique d'une élégance froide, Oracle suprême de l'horreur.\n\n"
            f'QUESTION DE L\'UTILISATEUR : "{user_question}"\n\n'
            f"DONNÉES LOCALES (Supabase) :\n{local_text}\n\n"
            f"DONNÉES WEB (Wikipédia) :\n{web_text}\n\n"
            "RÈGLES DE RÉDACTION :\n"
            "1. FIDÉLITÉ ABSOLUE AUX DONNÉES (règle suprême). Tu ne disposes QUE des "
            "DONNÉES LOCALES et DONNÉES WEB ci-dessus. Il t'est formellement INTERDIT "
            "d'inventer ou d'altérer le moindre fait. Reproduis les dates et les chiffres "
            "EXACTEMENT tels qu'ils sont écrits (une sortie '1979-05-25' se dit 1979, "
            "jamais 2024). Si un champ est absent ou vaut 'non renseigné', assume-le avec "
            "mépris ('les archives sont muettes sur ce point') — n'invente JAMAIS de valeur "
            "pour combler un trou. N'ajoute aucun fait qui ne figure pas dans les données.\n"
            "2. RÉALISATEUR & CASTING : les DONNÉES LOCALES n'en contiennent JAMAIS. "
            "Ne cite un réalisateur ou un acteur QUE s'il apparaît explicitement dans les "
            "DONNÉES WEB. En leur absence, déclare que les archives sont muettes — "
            "n'invente sous AUCUN prétexte un nom de réalisateur ou d'acteur.\n"
            "3. Réponds précisément à ce qui est demandé (calcul de survie, nombre de films, "
            "date, note, synopsis, ou infos web disponibles).\n"
            "4. Sois percutant et direct : **1 à 2 paragraphes maximum** (interdiction absolue de faire une dissertation de 10 lignes).\n"
            "5. Conserve ton ton sarcastique, sombre et hautain, fidèle à ton personnage."
            f"{correction}"
        )
    )

    sterile_command = HumanMessage(
        content="Génère ta réponse cynique en exploitant les données fournies et en restant concis."
    )

    response = llm_creative.invoke([system_prompt, sterile_command])
    return {"messages": [response]}


# --- 5. CONTRÔLE QUALITÉ (Le Juge) ---

# Années plausibles pour du cinéma (1800–2099). On évite ainsi de confondre une
# année avec un nombre de victimes (« 3000 morts ») hors de cette plage.
_YEAR_RE = re.compile(r"\b(?:1[89]\d{2}|20\d{2})\b")


def _extract_years(text: str) -> set[str]:
    """Extrait les années plausibles (1800–2099) d'un texte. Fonction pure."""
    return set(_YEAR_RE.findall(text))


def _detect_fabricated_years(narration: str, *sources: Any) -> set[str]:
    """Retourne les années citées dans la narration mais ABSENTES des sources.

    Garde-fou DÉTERMINISTE (testable unitairement, esprit router.py) : le Juge LLM
    (8B) peut laisser passer une date inventée, pas ce filtre. C'est lui qui a attrapé
    le « 2024 » sorti de nulle part alors que la source disait 1979.

    Limite assumée : un nombre à 4 chiffres dans la plage 1800–2099 qui ne serait pas
    une année (rare dans un texte d'1-2 paragraphes) pourrait être signalé à tort.
    """
    allowed: set[str] = set()
    for src in sources:
        allowed |= _extract_years(str(src))
    return _extract_years(narration) - allowed


def quality_control_node(state: AgentState) -> dict[str, Any]:
    """Audite la réponse de l'Écrivain sur DEUX plans : cohérence factuelle ET ton.

    Nouveauté : le Juge ne se contente plus de noter l'ambiance, il fact-checke le
    texte contre les données sources (SQL + Web) et rejette toute année/fait inventé.
    """
    messages = state["messages"]
    last_agent_message = messages[-1].content

    # Sources de vérité : EXACTEMENT les données que la Narration avait en main.
    local_lore = state.get("local_lore", {})
    web_data = state.get("web_anecdotes", [])

    # Même formatage texte propre que dans narration_node (évite ['...'] brut)
    local_text = (
        local_lore.get("faits_sql_bruts", "Aucune donnée locale.")
        if isinstance(local_lore, dict)
        else str(local_lore)
    )
    web_text = (
        "\n\n---\n\n".join(str(w) for w in web_data)
        if web_data
        else "Aucune donnée web disponible."
    )

    evaluator_llm = llm_judge.with_structured_output(EvaluationVerdict)

    audit_prompt = SystemMessage(
        content=(
            "Tu es HorRAGor, l'Auditeur Suprême des Ténèbres. Tu audites sur DEUX plans.\n\n"
            "1. FACT-CHECK (priorité absolue). Le texte ne doit affirmer QUE des faits "
            "présents dans les SOURCES ci-dessous. Toute donnée INVENTÉE ou ALTÉRÉE par "
            "rapport aux sources (année, date, budget, note) = verdict 'NON'. Vérifie "
            "SPÉCIALEMENT que l'ANNÉE citée dans le texte est bien celle des sources : une "
            "année qui n'apparaît pas dans les sources est une hallucination, rejette-la.\n"
            "2. RÉALISATEUR & CASTING. Les SOURCES LOCALES n'en contiennent JAMAIS. Si le "
            "texte nomme un réalisateur ou un acteur, ce nom DOIT figurer dans les SOURCES "
            "WEB ci-dessous ; s'il n'y est pas (a fortiori si les sources web sont vides), "
            "c'est une hallucination pure -> verdict 'NON'.\n"
            "3. TON. Le texte doit rester cynique, sombre et hautain (ni plat, ni gentil).\n\n"
            f"SOURCES LOCALES (vérité SQL) :\n{local_text}\n\n"
            f"SOURCES WEB (vérité scraper) :\n{web_text}\n\n"
            f'TEXTE À AUDITER : "{last_agent_message}"\n\n'
            "Rends 'NON' si le moindre fait est inventé/altéré OU si le ton est plat. "
            "Rends 'OUI' seulement si TOUT fait est sourcé ET le ton est bon. "
            "Rédige d'abord ton analyse, puis le verdict (OUI/NON) et la critique."
        )
    )
    verdict_obj = evaluator_llm.invoke([audit_prompt])

    # --- GARDE-FOU DÉTERMINISTE : années inventées (backstop du Juge LLM) ---
    fabricated = _detect_fabricated_years(last_agent_message, local_lore, web_data)
    if fabricated:
        annees = ", ".join(sorted(fabricated))
        print(
            f"🚨 [JUGE] Année(s) hallucinée(s) détectée(s) : {annees} "
            "(absente(s) des sources). Rejet forcé."
        )
        verdict_obj.grade = "NON"
        verdict_obj.critique = (
            f"Année(s) inventée(s) : {annees}. Ces années n'existent PAS dans les "
            "données sources. Reprends STRICTEMENT la date fournie par les sources locales."
        )

    print(
        f"\n⚖️ [JUGE] Analyse : {verdict_obj.analyse_preliminaire}\nVerdict : {verdict_obj.grade} | Critique : {verdict_obj.critique}\n"
    )

    verdict_dict = verdict_obj.model_dump()

    if verdict_obj.grade == "NON":
        # "REFUSÉ" est le marqueur compté par route_after_eval (coupe-circuit à 2).
        correction_message = HumanMessage(
            content=f"REFUSÉ. Motif : {verdict_obj.critique}"
        )
        return {"verdict": verdict_dict, "messages": [correction_message]}

    return {"verdict": verdict_dict}


# Le ToolNode connaît désormais AUSSI l'outil du Scraper.
# Le routage de retour (rag_agent vs scraper_agent) est géré par route_after_tools.
tools_node = ToolNode(rag_tools + scraper_tools)
