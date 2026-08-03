"""Tests unitaires pour src/tools/rag_tool.py.

_resolve_media est testée avec une session SQLAlchemy mockée —
pas de connexion Supabase réelle nécessaire.
"""

from unittest.mock import MagicMock

from src.tools.rag_tool import _resolve_media


def _make_media(title: str, horragor_id: str = "abc123") -> MagicMock:
    """Helper : crée un objet Media simulé."""
    m = MagicMock()
    m.title = title
    m.horragor_id = horragor_id
    m.release_date = "1979-05-25"
    m.director = "Ridley Scott"
    m.cast_top5 = "Tom Skerritt, Sigourney Weaver"
    m.genres = "Horror, Science Fiction"
    m.runtime = 117
    m.tagline = "In space no one can hear you scream."
    m.budget_tmdb = 11000000
    m.category = "Horreur"
    return m


class TestResolveMedia:
    def _make_session(self, exact_result=None, fallback_result=None):
        """Construit une session mock avec exact et fallback configurables."""
        session = MagicMock()
        query = MagicMock()
        session.query.return_value = query

        # Chaîne .filter().first() pour le match exact
        filter_mock = MagicMock()
        query.filter.return_value = filter_mock
        filter_mock.first.return_value = exact_result

        # Chaîne .filter().order_by().first() pour le fallback
        order_mock = MagicMock()
        filter_mock.order_by.return_value = order_mock
        order_mock.first.return_value = fallback_result

        return session

    def test_exact_match_by_title(self):
        alien = _make_media("Alien", "alien_id")
        session = self._make_session(exact_result=alien)
        result = _resolve_media(session, "Alien")
        assert result.title == "Alien"

    def test_exact_match_by_horragor_id(self):
        alien = _make_media("Alien", "alien_id_123")
        session = self._make_session(exact_result=alien)
        result = _resolve_media(session, "alien_id_123")
        assert result is alien

    def test_fallback_when_no_exact_match(self):
        """Sans match exact, utilise le fallback (plus court titre contenant la ref)."""
        alien = _make_media("Alien")
        session = self._make_session(exact_result=None, fallback_result=alien)
        result = _resolve_media(session, "Alien")
        assert result.title == "Alien"

    def test_returns_none_when_no_match(self):
        session = self._make_session(exact_result=None, fallback_result=None)
        result = _resolve_media(session, "Film Inexistant")
        assert result is None

    def test_strips_whitespace_from_reference(self):
        alien = _make_media("Alien")
        session = self._make_session(exact_result=alien)
        result = _resolve_media(session, "  Alien  ")
        assert result is not None

    def test_case_insensitive_exact_match(self):
        """Le match exact doit être insensible à la casse."""
        alien = _make_media("Alien")
        session = self._make_session(exact_result=alien)
        result = _resolve_media(session, "alien")
        assert result is not None

    def test_exact_beats_fallback(self):
        """Quand un match exact existe, il est retourné sans aller au fallback."""
        alien_exact = _make_media("Alien", "exact")
        alien_fallback = _make_media("Alienation", "fallback")
        session = self._make_session(exact_result=alien_exact, fallback_result=alien_fallback)
        result = _resolve_media(session, "Alien")
        assert result.horragor_id == "exact"
