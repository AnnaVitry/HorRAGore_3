import datetime

from langchain_core.tools import tool


@tool
def calculate_movie_age(release_year: int) -> str:
    """
    TOOL 4 : Le Calculateur Temporel.
    Utilise cet outil pour calculer mathématiquement l'âge d'un film.
    Passe uniquement l'année de sortie à 4 chiffres (ex: 1979) en argument.
    """
    print(f"   [MATH] Calcul temporel pour l'année : {release_year}...")
    current_year = datetime.datetime.now(datetime.UTC).year
    age = current_year - int(release_year)
    return f"Le film a exactement {age} ans."


@tool
def horror_survival_simulator(synopsis: str) -> str:
    """
    TOOL 5 : Le Simulateur de Survie.
    Outil ludique. Utilise cet outil si l'utilisateur demande s'il survivrait dans le film.
    Passe un court résumé de l'intrigue en argument.
    """
    print("   [GAME] Lancement de la simulation de survie...")
    return "Simulation terminée. Probabilité de survie : 4%. Cause probable : Mort atroce dans l'espace ou une cabane."
