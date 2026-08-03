"""Tests unitaires pour src/graph/router.py.

Le spec exige que le routage soit déterministe et testable unitairement
sans lancer le pipeline complet. Ces tests vérifient exactement ça.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END

from src.graph.router import (
    MAX_TOOL_LOOPS,
    route_after_eval,
    route_after_rag,
    route_after_scraper,
    route_after_tools,
)


def _make_ai_with_tool(tool_name: str) -> AIMessage:
    """Helper : crée un AIMessage avec un tool_call."""
    msg = AIMessage(content="")
    msg.tool_calls = [{"name": tool_name, "args": {}, "id": "test_1", "type": "tool_call"}]
    return msg


def _make_state(messages=None, is_sufficient=None, verdict=None):
    """Helper : construit un AgentState minimal."""
    state = {"messages": messages or [HumanMessage(content="test")]}
    if is_sufficient is not None:
        state["is_database_sufficient"] = is_sufficient
    if verdict is not None:
        state["verdict"] = verdict
    return state


# ==============================================================================
# route_after_rag
# ==============================================================================
class TestRouteAfterRag:
    def test_routes_to_tools_if_tool_calls(self):
        msg = _make_ai_with_tool("query_movie_metadata")
        state = _make_state(messages=[msg])
        assert route_after_rag(state) == "tools"

    def test_routes_to_narration_if_sufficient(self):
        state = _make_state(
            messages=[AIMessage(content="réponse")],
            is_sufficient=True
        )
        assert route_after_rag(state) == "narration_agent"

    def test_routes_to_scraper_if_not_sufficient(self):
        state = _make_state(
            messages=[AIMessage(content="réponse")],
            is_sufficient=False
        )
        assert route_after_rag(state) == "scraper_agent"

    def test_default_to_narration_if_no_flag(self):
        """Sans flag is_database_sufficient, on va en Narration (défaut True)."""
        state = _make_state(messages=[AIMessage(content="réponse")])
        assert route_after_rag(state) == "narration_agent"

    def test_tool_calls_take_priority_over_flag(self):
        """Tool calls priment sur is_database_sufficient=False."""
        msg = _make_ai_with_tool("query_movie_metadata")
        state = _make_state(messages=[msg], is_sufficient=False)
        assert route_after_rag(state) == "tools"


# ==============================================================================
# route_after_scraper
# ==============================================================================
class TestRouteAfterScraper:
    def test_routes_to_tools_if_tool_calls(self):
        msg = _make_ai_with_tool("scrape_detailed_synopsis")
        state = _make_state(messages=[msg])
        assert route_after_scraper(state) == "tools"

    def test_routes_to_narration_if_no_tool_calls(self):
        state = _make_state(messages=[AIMessage(content="butin web récolté")])
        assert route_after_scraper(state) == "narration_agent"


# ==============================================================================
# route_after_tools
# ==============================================================================
class TestRouteAfterTools:
    def test_returns_rag_agent_for_rag_tool(self):
        msg = _make_ai_with_tool("query_movie_metadata")
        state = _make_state(messages=[HumanMessage(content="test"), msg])
        assert route_after_tools(state) == "rag_agent"

    def test_returns_scraper_agent_for_scraper_tool(self):
        msg = _make_ai_with_tool("scrape_detailed_synopsis")
        state = _make_state(messages=[HumanMessage(content="test"), msg])
        assert route_after_tools(state) == "scraper_agent"

    def test_coupe_circuit_at_max_loops(self):
        """Après MAX_TOOL_LOOPS appels scraper, force vers la Narration."""
        scraper_calls = [_make_ai_with_tool("scrape_detailed_synopsis")] * MAX_TOOL_LOOPS
        state = _make_state(messages=scraper_calls)
        assert route_after_tools(state) == "narration_agent"

    def test_coupe_circuit_not_triggered_below_max(self):
        """Sous MAX_TOOL_LOOPS appels scraper, on revient au scraper."""
        scraper_calls = [_make_ai_with_tool("scrape_detailed_synopsis")] * (MAX_TOOL_LOOPS - 1)
        state = _make_state(messages=scraper_calls)
        assert route_after_tools(state) == "scraper_agent"

    def test_rag_calls_dont_trigger_coupe_circuit(self):
        """Les appels RAG ne comptent PAS dans le coupe-circuit scraper."""
        rag_calls = [_make_ai_with_tool("query_movie_metadata")] * 10
        scraper_call = _make_ai_with_tool("scrape_detailed_synopsis")
        state = _make_state(messages=rag_calls + [scraper_call])
        # 1 seul appel scraper -> pas de coupe-circuit -> retourne scraper_agent
        assert route_after_tools(state) == "scraper_agent"

    def test_fallback_to_rag_if_no_ai_message(self):
        state = _make_state(messages=[HumanMessage(content="test")])
        assert route_after_tools(state) == "rag_agent"


# ==============================================================================
# route_after_eval
# ==============================================================================
class TestRouteAfterEval:
    def test_routes_to_end_on_oui(self):
        state = _make_state(verdict={"grade": "OUI", "critique": ""})
        assert route_after_eval(state) == END

    def test_routes_to_narration_on_non(self):
        state = _make_state(
            messages=[HumanMessage(content="test")],
            verdict={"grade": "NON", "critique": "Trop plat"}
        )
        assert route_after_eval(state) == "narration_agent"

    def test_coupe_circuit_at_2_refus(self):
        """Après 2 REFUSÉ dans les messages, force END même avec verdict NON."""
        messages = [
            HumanMessage(content="test"),
            HumanMessage(content="REFUSÉ. Motif : trop plat."),
            HumanMessage(content="REFUSÉ. Motif : encore trop plat."),
        ]
        state = _make_state(
            messages=messages,
            verdict={"grade": "NON", "critique": "Toujours plat"}
        )
        assert route_after_eval(state) == END

    def test_no_coupe_circuit_at_1_refus(self):
        messages = [
            HumanMessage(content="test"),
            HumanMessage(content="REFUSÉ. Motif : trop plat."),
        ]
        state = _make_state(
            messages=messages,
            verdict={"grade": "NON", "critique": "Trop plat"}
        )
        assert route_after_eval(state) == "narration_agent"

    def test_no_verdict_routes_to_narration(self):
        state = _make_state(messages=[HumanMessage(content="test")])
        assert route_after_eval(state) == "narration_agent"
