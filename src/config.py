import os

from dotenv import load_dotenv

# 1. On calcule dynamiquement le chemin absolu vers la racine du projet
# __file__ correspond à src/config.py -> on remonte de deux dossiers pour atteindre la racine
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")

# 2. On force dotenv à lire CE fichier exact
load_dotenv(dotenv_path=ENV_PATH)

# 3. Validation de la connexion Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")

if not SUPABASE_URL:
    raise ValueError(
        f"🛑 ERREUR CRITIQUE : SUPABASE_URL est introuvable.\n(On a cherché le fichier .env exactement ici : {ENV_PATH})"
    )

# --- CONSTANTES DE L'APPLICATION ---
# On utilise aussi BASE_DIR pour le parquet, comme ça il le trouvera à 100%
PARQUET_FILE_PATH = os.path.join(BASE_DIR, "data", "horragor_final_data.parquet")

# Paramètres d'Intelligence Artificielle
EMBEDDING_MODEL_NAME = "nomic-embed-text"
LLM_MODEL_NAME = "llama3.2:3b"
