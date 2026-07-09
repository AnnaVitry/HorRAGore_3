import os

import faiss
import numpy as np  # noqa: F401
import polars as pl  # noqa: F401
from dotenv import load_dotenv
from langchain_community.vectorstores import PGVector

# Imports LangChain
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings

# Imports Base de données
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker

# Import de tes tables depuis ton fichier à la racine
from supabase_db import ContentStore, Media, Score


class FastMovieRouter:
    """
    Routeur vectoriel local.
    Sert de mémoire rapide pour valider l'existence d'un film.
    """

    def __init__(self, parquet_path: str):
        print("🧠 Initialisation de la mémoire éphémère (Routeur FAISS)...")
        self.embeddings_model = OllamaEmbeddings(model="nomic-embed-text")
        self.dimension = 768

        self.index = faiss.IndexFlatL2(self.dimension)
        self.movie_ids = []
        self.movie_titles = []

        self._load_and_index(parquet_path)


# --- INITIALISATION DE LA CONNEXION ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
if not SUPABASE_URL:
    raise ValueError("⚠️ SUPABASE_URL introuvable dans le .env")

# On crée le moteur qui servira à nos deux outils
engine = create_engine(SUPABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# --- OUTIL 1 : SQL (Version Robuste) ---
@tool
def query_movie_metadata(movie_reference: str) -> str:
    """
    Utilise cet outil pour obtenir les métadonnées d'un film.
    Tu peux lui fournir soit l'ID unique, soit directement le TITRE du film (ex: 'Alien').
    """
    print(f"   [SQL] Interrogation de Supabase pour : {movie_reference}...")
    session = SessionLocal()
    try:
        # Recherche par ID exact OU par ressemblance sur le titre (insensible à la casse)
        media = (
            session.query(Media)
            .filter(
                or_(
                    Media.horragor_id == movie_reference,
                    Media.title.ilike(f"%{movie_reference}%"),
                )
            )
            .first()
        )

        if not media:
            return f"Aucune métadonnée trouvée en base pour '{movie_reference}'."

        score_record = session.query(Score).filter_by(media_id=media.id).first()
        note = score_record.value if score_record else "Non renseignée"

        return (
            f"Titre Exact: {media.title}, Sortie: {media.release_date}, "
            f"Univers: {media.category}, Budget: {media.budget}$, Note: {note}/10. "
            f"(ID officiel pour info: {media.horragor_id})"
        )
    except Exception as e:
        return f"Erreur SQL : {str(e)}"
    finally:
        session.close()


# --- OUTIL 2 : PGVECTOR ---
@tool
def find_similar_horror_movies(movie_id: str) -> str:
    """
    Utilise cet outil UNIQUEMENT pour recommander des films similaires.
    Tu DOIS LUI FOURNIR L'IDENTIFIANT UNIQUE DU FILM (movie_id).
    """
    print(f"   [PGVECTOR] Recherche de similarité pour l'ID : {movie_id}...")
    session = SessionLocal()
    try:
        media = session.query(Media).filter_by(horragor_id=movie_id).first()
        if not media:
            return "Film introuvable pour la recommandation."

        content = session.query(ContentStore).filter_by(media_id=media.id).first()
        if not content or not content.synopsis:
            return f"Aucun synopsis pour {media.title}. Recommandation impossible."

        # Préparation de l'URL pour PGVector (doit commencer par postgresql+psycopg2)
        conn_string = SUPABASE_URL.replace("postgresql://", "postgresql+psycopg2://")

        embeddings = OllamaEmbeddings(model="nomic-embed-text")
        vectorstore = PGVector(
            connection_string=conn_string,
            collection_name="horragor_vectors",
            embedding_function=embeddings,
            use_jsonb=True,
        )

        results = vectorstore.similarity_search(content.synopsis, k=4)

        recommandations = [
            f"- {doc.page_content[:150]}..."
            for doc in results
            if media.title not in doc.page_content
        ]

        return f"Recommandations pour '{media.title}' :\n" + "\n".join(recommandations)
    except Exception as e:
        return f"Erreur vectorielle : {str(e)}"
    finally:
        session.close()
