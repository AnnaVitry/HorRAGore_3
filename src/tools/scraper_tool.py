"""Scraper Wikipédia — API REST directe, sans la lib `wikipedia`.

Pourquoi remplacer la lib `wikipedia` ?
  - Elle fait des appels MediaWiki avec un User-Agent générique souvent rate-limité.
  - Sa gestion des erreurs réseau est opaque (JSONDecodeError silencieux).
  - Elle ne permet pas de configurer timeout, headers, ni retry backoff.

On appelle directement deux endpoints officiels de Wikipédia :
  1. REST /page/summary/{title}  → intro structurée (titre, extrait, URL).
  2. Action API ?action=query… → sections de production/casting en wikitext brut,
     nettoyé avec une regex simple pour retirer les balises wiki.
"""

import re
import time

import requests
from langchain_core.tools import tool

# --- Configuration réseau ---
_HEADERS = {
    # User-Agent explicite : Wikipédia l'exige pour ne pas être rate-limité.
    "User-Agent": "HorRAGor/3.0 (educational project; python-requests)",
    "Accept": "application/json",
}
_TIMEOUT = 8  # secondes par requête
_RETRY_DELAYS = [1, 3]  # délais entre tentatives (2 retries max)

# Sections Wikipédia anglophones à extraire, par ordre de priorité.
_TARGET_SECTIONS = [
    "Production",
    "Filming",
    "Casting",
    "Development",
    "Making",
    "Cast",
    "Release",
    "Background",
]

_WIKI_CLEAN_RE = re.compile(
    r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]"  # [[lien|texte]] -> texte
    r"|\{\{[^}]*\}\}"  # {{template}} -> supprimé
    r"|<[^>]+>"  # balises HTML -> supprimées
    r"|'{2,3}"  # '' ou ''' (gras/italique) -> supprimés
)


def _clean_wikitext(text: str) -> str:
    """Supprime les balises wikitext les plus courantes, garde le texte lisible."""
    cleaned = _WIKI_CLEAN_RE.sub(lambda m: m.group(1) or "", text)
    # Compresse les lignes vides multiples
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _pick_best_result(results: list[str], movie_title: str) -> str:
    """Sélection déterministe : exact > (film > fallback results[0]."""
    title_lower = movie_title.strip().lower()
    for r in results:
        if r.strip().lower() == title_lower:
            return r
    for r in results:
        if title_lower in r.lower() and "(film" in r.lower():
            return r
    return results[0]


def _get_with_retry(url: str, params: dict | None = None) -> requests.Response:
    """GET avec retry exponentiel sur erreur réseau transitoire."""
    last_exc: Exception | None = None
    attempts = [0] + _RETRY_DELAYS
    for i, delay in enumerate(attempts):
        if delay:
            print(f"   ↻ [SCRAPER] Retry {i}/{len(_RETRY_DELAYS)} dans {delay}s…")
            time.sleep(delay)
        try:
            r = requests.get(url, headers=_HEADERS, params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            last_exc = e
            print(f"   ⚠️ [SCRAPER] Tentative {i + 1} échouée : {type(e).__name__}")
    raise last_exc  # type: ignore[misc]


def _search_titles(query: str) -> list[str]:
    """Recherche de titres via l'Action API (opensearch)."""
    r = _get_with_retry(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "opensearch",
            "search": query,
            "limit": 8,
            "namespace": 0,
            "format": "json",
        },
    )
    data = r.json()
    # opensearch retourne [query, [titres], [descriptions], [urls]]
    return data[1] if len(data) > 1 else []


def _get_summary(title: str) -> str:
    """Récupère l'intro structurée via l'API REST (plus fiable que wikitext)."""
    encoded = title.replace(" ", "_")
    r = _get_with_retry(f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}")
    data = r.json()
    return data.get("extract", "").strip()


def _get_sections(title: str) -> str:
    """Récupère les sections de production en wikitext, nettoyées."""
    parts: list[str] = []
    for section_name in _TARGET_SECTIONS:
        try:
            # On cherche le numéro de la section cible d'abord
            r2 = _get_with_retry(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "parse",
                    "page": title,
                    "prop": "sections",
                    "format": "json",
                },
            )
            sections = r2.json().get("parse", {}).get("sections", [])
            section_num = next(
                (
                    s["index"]
                    for s in sections
                    if s.get("line", "").strip().lower() == section_name.lower()
                ),
                None,
            )
            if section_num is None:
                continue

            r3 = _get_with_retry(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "parse",
                    "page": title,
                    "prop": "wikitext",
                    "section": section_num,
                    "format": "json",
                },
            )
            wikitext = r3.json().get("parse", {}).get("wikitext", {}).get("*", "")
            if wikitext and len(wikitext.strip()) > 80:
                cleaned = _clean_wikitext(wikitext)
                parts.append(f"[{section_name}]\n{cleaned[:600]}")
                if sum(len(p) for p in parts) >= 1800:
                    break
        except requests.exceptions.RequestException:
            continue  # section introuvable ou erreur réseau sur cette section -> on passe

    return "\n\n".join(parts)


@tool
def scrape_detailed_synopsis(movie_title: str) -> str:
    """Scrape Wikipédia (EN) pour extraire réalisateur, casting et anecdotes de production.

    Utilise l'API REST officielle directement (sans la lib `wikipedia`)
    pour éviter les rate-limits et les erreurs réseau opaques.
    """
    print(f"🔍 [SCRAPER] Recherche Wikipédia : '{movie_title} (film)'")

    try:
        # 1. Recherche du meilleur titre Wikipédia
        results = _search_titles(f"{movie_title} (film)")
        if not results:
            results = _search_titles(movie_title)
        if not results:
            return f"Aucune page Wikipédia trouvée pour '{movie_title}'."

        print(f"   Résultats bruts : {results[:5]}")
        best = _pick_best_result(results, movie_title)
        print(f"   Meilleur résultat retenu : {best!r}")

        # 2. Intro (contient réalisateur, date, genre, casting principal)
        summary = _get_summary(best)
        print(f"   Intro récupérée : {len(summary)} car.")

        # 3. Sections de production
        sections = _get_sections(best)
        print(f"   Sections production : {len(sections)} car.")

        if not summary and not sections:
            return f"Page Wikipédia trouvée ('{best}') mais contenu vide."

        result = f"[Résumé]\n{summary}\n\n{sections}".strip()[:3000]
        print(f"🕸️ [SCRAPER] Butin extrait : {len(result)} car. depuis '{best}'")
        return result

    except requests.exceptions.RequestException as e:
        print(
            f"❌ [SCRAPER] Erreur réseau définitive pour '{movie_title}' : {type(e).__name__}"
        )
        return (
            f"L'API Wikipedia est inaccessible pour '{movie_title}' "
            "(erreur réseau après plusieurs tentatives). "
            "Aucune donnée web disponible."
        )
    except (ValueError, KeyError, requests.exceptions.JSONDecodeError) as e:
        print(f"❌ [SCRAPER] Erreur de parsing pour '{movie_title}' : {e}")
        return f"Erreur de parsing lors du scraping de '{movie_title}' : {e!s}"
