"""Tests unitaires pour src/tools/scraper_tool.py.

Couvre les fonctions pures sans réseau :
  - _clean_wikitext
  - _pick_best_result

Les fonctions réseau (_get_with_retry, _get_summary, _get_sections)
sont testées via mock pour ne pas dépendre de Wikipédia.
"""



from src.tools.scraper_tool import _clean_wikitext, _pick_best_result


# ==============================================================================
# _pick_best_result
# ==============================================================================
class TestPickBestResult:
    def test_exact_match_wins(self):
        results = ["Alienation", "Alien Love", "Alien", "Alien Nation"]
        assert _pick_best_result(results, "Alien") == "Alien"

    def test_exact_match_case_insensitive(self):
        results = ["ALIEN", "Alien Love"]
        assert _pick_best_result(results, "alien") == "ALIEN"

    def test_film_suffix_wins_over_fallback(self):
        results = ["Alien Love", "Alien Horde", "Alien (film)"]
        assert _pick_best_result(results, "Alien") == "Alien (film)"

    def test_film_year_suffix_matches(self):
        """(film, 1979) doit être reconnu comme match film."""
        results = ["Alien Love", "Alien Horde", "Alien (film, 1979)"]
        assert _pick_best_result(results, "Alien") == "Alien (film, 1979)"

    def test_film_series_suffix_matches(self):
        results = ["Alien Love", "Alien (film series)"]
        assert _pick_best_result(results, "Alien") == "Alien (film series)"

    def test_fallback_to_first_result(self):
        results = ["Random stuff", "More stuff"]
        assert _pick_best_result(results, "Alien") == "Random stuff"

    def test_the_shining(self):
        results = ["The Shining (film)", "The Shining (novel)", "The Shining (miniseries)"]
        assert _pick_best_result(results, "The Shining") == "The Shining (film)"

    def test_exact_match_priority_over_film_suffix(self):
        """Match exact prime sur (film) même si les deux sont présents."""
        results = ["Alien", "Alien (film)"]
        assert _pick_best_result(results, "Alien") == "Alien"

    def test_single_result(self):
        assert _pick_best_result(["Alien"], "Alien") == "Alien"

    def test_halloween(self):
        results = ["Halloween (film)", "Halloween (franchise)", "Halloween II"]
        assert _pick_best_result(results, "Halloween") == "Halloween (film)"


# ==============================================================================
# _clean_wikitext
# ==============================================================================
class TestCleanWikitext:
    def test_removes_internal_links(self):
        assert _clean_wikitext("[[Ridley Scott]] a réalisé") == "Ridley Scott a réalisé"

    def test_removes_piped_links(self):
        assert _clean_wikitext("[[Ridley Scott|Scott]]") == "Scott"

    def test_removes_templates(self):
        result = _clean_wikitext("{{cite web|url=example.com}} texte")
        assert "{{" not in result
        assert "texte" in result

    def test_removes_bold(self):
        assert _clean_wikitext("'''Alien'''") == "Alien"

    def test_removes_italic(self):
        assert _clean_wikitext("''Alien''") == "Alien"

    def test_removes_html_tags(self):
        assert _clean_wikitext("<ref>citation</ref>") == "citation"

    def test_empty_string(self):
        assert _clean_wikitext("") == ""

    def test_plain_text_unchanged(self):
        text = "Alien is a 1979 science fiction horror film."
        assert _clean_wikitext(text) == text

    def test_compresses_multiple_newlines(self):
        result = _clean_wikitext("ligne1\n\n\n\nligne2")
        assert "\n\n\n" not in result
        assert "ligne1" in result
        assert "ligne2" in result
