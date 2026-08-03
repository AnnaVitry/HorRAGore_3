"""Tests unitaires pour src/graph/nodes.py.

Couvre les 4 fonctions pures exportables :
  - _lore_looks_empty
  - _extract_title_from_facts
  - _extract_years
  - _detect_fabricated_years

Aucune dépendance DB, Ollama ou réseau — 100% unitaire.
"""


# Import direct des fonctions pures (pas d'import du module entier
# pour éviter d'initialiser ChatOllama au niveau module)
from src.graph.nodes import (
    _detect_fabricated_years,
    _extract_title_from_facts,
    _extract_years,
    _lore_looks_empty,
)


# ==============================================================================
# _lore_looks_empty
# ==============================================================================
class TestLoreLooksEmpty:
    def test_none_is_empty(self):
        assert _lore_looks_empty(None) is True

    def test_empty_string_is_empty(self):
        assert _lore_looks_empty("") is True

    def test_empty_dict_is_empty(self):
        assert _lore_looks_empty({}) is True

    def test_aucune_donnee_is_empty(self):
        assert _lore_looks_empty("aucune donnée trouvée") is True

    def test_desole_is_empty(self):
        assert _lore_looks_empty("Désolé, aucun résultat.") is True

    def test_valid_lore_is_not_empty(self):
        lore = "Titre Exact: Alien, Sortie: 1979-05-25, Réalisateur: Ridley Scott"
        assert _lore_looks_empty(lore) is False

    def test_dict_with_content_is_not_empty(self):
        lore = {"faits_sql_bruts": "Titre Exact: Alien, Sortie: 1979-05-25"}
        assert _lore_looks_empty(lore) is False

    def test_none_keyword_in_lore_is_empty(self):
        assert _lore_looks_empty("none") is True

    def test_aucun_resultat_is_empty(self):
        assert _lore_looks_empty("aucun résultat trouvé en base") is True


# ==============================================================================
# _extract_title_from_facts
# ==============================================================================
class TestExtractTitleFromFacts:
    def test_extracts_simple_title(self):
        facts = "Titre Exact: Alien, Sortie: 1979-05-25, Univers: Horreur"
        assert _extract_title_from_facts(facts) == "Alien"

    def test_extracts_title_with_spaces(self):
        facts = "Titre Exact: The Shining, Sortie: 1980-05-23"
        assert _extract_title_from_facts(facts) == "The Shining"

    def test_extracts_title_with_colon(self):
        facts = "Titre Exact: Alien: Romulus, Sortie: 2024-08-16"
        assert _extract_title_from_facts(facts) == "Alien: Romulus"

    def test_returns_none_if_no_title(self):
        assert _extract_title_from_facts("Aucune donnée trouvée") is None

    def test_returns_none_on_empty_string(self):
        assert _extract_title_from_facts("") is None

    def test_returns_none_on_wrong_format(self):
        assert _extract_title_from_facts("title=Alien, date=1979") is None

    def test_strips_whitespace(self):
        facts = "Titre Exact:   Alien  , Sortie: 1979"
        assert _extract_title_from_facts(facts) == "Alien"

    def test_extracts_from_dict_str(self):
        # Cas réel : local_lore est un dict converti en str
        facts = "{'faits_sql_bruts': 'Titre Exact: Halloween, Sortie: 1978'}"
        assert _extract_title_from_facts(facts) == "Halloween"


# ==============================================================================
# _extract_years
# ==============================================================================
class TestExtractYears:
    def test_extracts_single_year(self):
        assert _extract_years("Film sorti en 1979.") == {"1979"}

    def test_extracts_multiple_years(self):
        assert _extract_years("Sorti en 1979, suite en 1986.") == {"1979", "1986"}

    def test_ignores_out_of_range_numbers(self):
        # 3000 morts, 500 spectateurs — pas des années
        assert _extract_years("3000 morts, 500 spectateurs.") == set()

    def test_extracts_2000s_year(self):
        assert _extract_years("Film de 2024.") == {"2024"}

    def test_empty_string_returns_empty_set(self):
        assert _extract_years("") == set()

    def test_no_year_in_text(self):
        assert _extract_years("Aucune date mentionnée.") == set()

    def test_boundary_1800(self):
        assert "1800" in _extract_years("Depuis 1800.")

    def test_boundary_2099(self):
        assert "2099" in _extract_years("Jusqu'en 2099.")

    def test_out_of_boundary_1799(self):
        assert "1799" not in _extract_years("En 1799.")

    def test_out_of_boundary_2100(self):
        assert "2100" not in _extract_years("En 2100.")


# ==============================================================================
# _detect_fabricated_years
# ==============================================================================
class TestDetectFabricatedYears:
    def test_detects_fabricated_year(self):
        """Cas réel : Narration dit 2024, source dit 1979."""
        narration = "Ce film sorti en 2024 est un classique."
        source = {"faits_sql_bruts": "Sortie: 1979-05-25"}
        result = _detect_fabricated_years(narration, source)
        assert "2024" in result
        assert "1979" not in result

    def test_no_fabrication_when_year_matches(self):
        narration = "Ce film de 1979 est terrifiant."
        source = {"faits_sql_bruts": "Sortie: 1979-05-25"}
        assert _detect_fabricated_years(narration, source) == set()

    def test_year_from_web_data_is_allowed(self):
        """Une année absente du SQL mais présente dans le web n'est pas une hallucination."""
        narration = "Tourné en 1978, sorti en 1979."
        local = {"faits_sql_bruts": "Sortie: 1979-05-25"}
        web = ["Filming began in 1978 at Shepperton Studios."]
        assert _detect_fabricated_years(narration, local, web) == set()

    def test_multiple_sources(self):
        narration = "Film de 1979, note 8.17."
        local = {"faits_sql_bruts": "Sortie: 1979-05-25, Note: 8.17/10"}
        assert _detect_fabricated_years(narration, local) == set()

    def test_empty_narration(self):
        assert _detect_fabricated_years("", {"faits_sql_bruts": "1979"}) == set()

    def test_no_year_in_narration(self):
        narration = "Un film terrifiant sans date mentionnée."
        source = {"faits_sql_bruts": "Sortie: 1979-05-25"}
        assert _detect_fabricated_years(narration, source) == set()

    def test_two_fabricated_years(self):
        narration = "Sorti en 2020, suite en 2022."
        source = {"faits_sql_bruts": "Sortie: 1979-05-25"}
        result = _detect_fabricated_years(narration, source)
        assert result == {"2020", "2022"}

    def test_real_run_alien(self):
        """Reproduit exactement le bug qu'on a debuggé : 2024 au lieu de 1979."""
        narration = "date de sortie : 25 juin 2024"
        local = {"faits_sql_bruts": "Titre Exact: Alien, Sortie: 1979-05-25"}
        web: list = []
        result = _detect_fabricated_years(narration, local, web)
        assert "2024" in result
        assert "1979" not in result
