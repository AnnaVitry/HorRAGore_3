import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool


# --- OUTIL 3 : SCRAPER ---
@tool
def scrape_detailed_synopsis(movie_title: str) -> str:
    """
    Utilise cet outil SEULEMENT si l'utilisateur demande des anecdotes précises.
    Fournis le titre COMPLET du film.
    """
    print(f"   [WEB] Scraping Wikipédia activé pour : {movie_title}...")
    try:
        url = f"https://fr.wikipedia.org/wiki/{movie_title.replace(' ', '_')}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = soup.find_all("p")
            summary = " ".join([p.text for p in paragraphs[0:2] if len(p.text) > 20])
            return summary[:800] + "... [FIN DU SCRAPING]"
        return "Impossible d'accéder à la page Wikipédia."
    except Exception as e:
        return f"Erreur réseau : {e}"
