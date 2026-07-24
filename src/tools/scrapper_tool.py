import wikipedia
from langchain_core.tools import tool


# --- OUTIL 3 : SCRAPER ---
@tool
def scrape_detailed_synopsis(movie_title: str) -> str:
    """Outil de scraping Wikipédia blindé contre les homonymies."""

    # 1. Configurer l'API sur la version anglophone, souvent plus riche en anecdotes de production
    wikipedia.set_lang("en")

    # 2. Forcer le contexte cinématographique pour éviter la biologie ou la littérature
    search_query = f"{movie_title} (film)"

    try:
        # 3. Chercher les correspondances
        results = wikipedia.search(search_query)

        if not results:
            # Fallback sur le titre brut si "(film)" ne donne rien
            results = wikipedia.search(movie_title)
            if not results:
                return f"Aucune donnée trouvée sur le web pour : {movie_title}."

        # 4. Cibler le premier résultat le plus pertinent
        best_match = results[0]
        page = wikipedia.page(best_match, auto_suggest=False)

        # 5. Extraction chirurgicale des anecdotes de tournage
        target_sections = ["Production", "Filming", "Casting", "Development"]
        extracted_text = ""

        # On fouille la page pour trouver la première section technique disponible
        for section in target_sections:
            section_content = page.section(section)
            if section_content:
                extracted_text = f"Infos de tournage ({section}) : {section_content}"
                break

        # Fallback : si la page est courte et n'a pas ces sections spécifiques
        if not extracted_text:
            # On ignore les 1500 premiers caractères (souvent l'intro et le synopsis)
            extracted_text = page.content[1500:4500]

        # On limite toujours la taille pour ne pas surcharger la mémoire de Llama 3.1
        return extracted_text[:3000]

    except wikipedia.exceptions.DisambiguationError as e:
        # Gestion des pages d'homonymie (on prend la première option proposée par l'API)
        try:
            page = wikipedia.page(e.options[0], auto_suggest=False)
            return page.content[:3000]
        except wikipedia.exceptions.DisambiguationError:
            return f"Échec de résolution d'homonymie pour : {movie_title}."

    except wikipedia.exceptions.WikipediaException as e:
        return f"Erreur de l'API Wikipédia : {e!s}"
