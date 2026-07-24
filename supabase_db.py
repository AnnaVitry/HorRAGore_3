import os

import pandas as pd  # noqa: F401
import polars as pl
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,  # Permet d'exécuter des requêtes SQL brutes
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# import du config avec les variables
from src.config import PARQUET_FILE_PATH, SUPABASE_URL

Base = declarative_base()

# =====================================================================
# --- STRUCTURE 3NF (Modèle Physique de Données) ---
# =====================================================================


class Media(Base):
    __tablename__ = "medias"
    id = Column(Integer, primary_key=True)
    # --- AJOUT CRITIQUE : Notre identifiant unique universel ---
    horragor_id = Column(String(100), unique=True, nullable=False, index=True)

    title = Column(String(255), nullable=False)
    release_date = Column(Date)
    category = Column(String(50))  # Utile pour stocker "Sci-Fi" ou "Horreur" !
    budget = Column(BigInteger, default=0)
    revenue = Column(BigInteger, default=0)

    metadata_book = relationship(
        "BookInfo", back_populates="media", uselist=False, cascade="all, delete-orphan"
    )
    content = relationship(
        "ContentStore",
        back_populates="media",
        uselist=False,
        cascade="all, delete-orphan",
    )
    scores = relationship("Score", back_populates="media", cascade="all, delete-orphan")


class BookInfo(Base):
    __tablename__ = "book_info"
    id = Column(Integer, primary_key=True)
    media_id = Column(Integer, ForeignKey("medias.id"))
    author = Column(String(255))
    isbn = Column(String(20), nullable=True)
    media = relationship("Media", back_populates="metadata_book")


class ContentStore(Base):
    __tablename__ = "content_store"
    id = Column(Integer, primary_key=True)
    media_id = Column(Integer, ForeignKey("medias.id"))
    synopsis = Column(Text)
    consensus = Column(Text)
    media = relationship("Media", back_populates="content")


class Score(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True)
    media_id = Column(Integer, ForeignKey("medias.id"))
    provider = Column(String(50))
    value = Column(Float)
    media = relationship("Media", back_populates="scores")


# =====================================================================
# --- LOGIQUE D'ALIMENTATION ET EXPORT ---
# =====================================================================

engine = create_engine(SUPABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    print("🗄️ Initialisation du MPD (Modèle Physique de Données)...")

    # --- LA SOLUTION DE FORCE BRUTE (CASCADE) ---
    print("🧨 Nettoyage absolu en cours (Drop CASCADE)...")
    with engine.begin() as conn:
        # On force Supabase à détruire toutes les tables
        conn.execute(
            text(
                "DROP TABLE IF EXISTS movie_info, book_info, content_store, scores, medias CASCADE;"
            )
        )

    print(
        "🏗️ Reconstruction des tables avec le nouveau schéma (incluant horragor_id)..."
    )
    Base.metadata.create_all(bind=engine)

    # =====================================================================
    # --- SUPABASE POSTGRE API : SÉCURISATION RLS AUTOMATISÉE ---
    # =====================================================================
    print("🛡️ Sécurisation de l'API Supabase (Activation RLS et Politiques)...")
    with engine.begin() as conn:
        # 1. Activation du RLS pour verrouiller l'API
        conn.execute(text("ALTER TABLE public.medias ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE public.scores ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE public.book_info ENABLE ROW LEVEL SECURITY;"))
        conn.execute(
            text("ALTER TABLE public.content_store ENABLE ROW LEVEL SECURITY;")
        )

        # 2. Création des politiques "Lecture Seule" pour le monde extérieur (Front-End)
        conn.execute(
            text(
                'CREATE POLICY "Lecture publique medias" ON public.medias FOR SELECT TO public USING (true);'
            )
        )
        conn.execute(
            text(
                'CREATE POLICY "Lecture publique scores" ON public.scores FOR SELECT TO public USING (true);'
            )
        )
        conn.execute(
            text(
                'CREATE POLICY "Lecture publique book_info" ON public.book_info FOR SELECT TO public USING (true);'
            )
        )
        conn.execute(
            text(
                'CREATE POLICY "Lecture publique content_store" ON public.content_store FOR SELECT TO public USING (true);'
            )
        )

    print("🔒 La base est désormais sécurisée en lecture seule pour l'API.")


def save_to_supabase(reconciled_records: list):
    session = SessionLocal()
    print(
        f"💾 Insertion massive OPTIMISÉE (Batch) de {len(reconciled_records)} entités..."
    )

    try:
        # 1. L'ASTUCE DE GÉNIE : On télécharge tous les IDs existants en UNE SEULE requête !
        print("⏳ Vérification de l'idempotence (1 seule requête réseau)...")
        existing_ids = {row[0] for row in session.query(Media.horragor_id).all()}

        inserted_count = 0
        skipped_count = 0

        for rec in reconciled_records:
            if not rec.get("horragor_id"):
                continue

            # La vérification se fait maintenant instantanément dans la RAM de votre PC
            if rec["horragor_id"] in existing_ids:
                skipped_count += 1
                continue

            # --- Création de l'objet (Uniquement pour les NOUVEAUX films) ---
            dt = None
            if rec.get("release_date"):
                try:
                    from datetime import date

                    dt = date.fromisoformat(rec["release_date"])
                except ValueError as e:
                    print(f"⚠️ Format de date invalide ignoré : {e}")
                    dt = None  # Ou toute autre logique par défaut

            new_media = Media(
                horragor_id=rec["horragor_id"],
                title=rec["title"],
                release_date=dt,
                category=rec.get("source_universe", "Inconnu"),
                budget=rec.get("budget", 0) if rec.get("budget") else 0,
                revenue=rec.get("revenue", 0) if rec.get("revenue") else 0,
            )
            session.add(new_media)
            session.flush()  # On récupère l'ID relationnel

            if rec.get("is_book"):
                session.add(
                    BookInfo(media_id=new_media.id, author=rec.get("author", "Inconnu"))
                )

            session.add(
                ContentStore(
                    media_id=new_media.id,
                    synopsis=rec.get("overview"),
                    consensus=rec.get("rt_consensus"),
                )
            )

            if rec.get("vote_average"):
                session.add(
                    Score(
                        media_id=new_media.id,
                        provider="TMDB",
                        value=float(rec["vote_average"]),
                    )
                )
            if rec.get("rt_score"):
                session.add(
                    Score(
                        media_id=new_media.id,
                        provider="RottenTomatoes",
                        value=float(rec["rt_score"]),
                    )
                )

            inserted_count += 1

            # 2. L'AUTRE ASTUCE : On valide par lots de 1000 pour soulager la RAM du serveur Supabase
            if inserted_count % 1000 == 0:
                session.commit()
                print(
                    f"   🚀 [Batch] {inserted_count} films expédiés et validés en base..."
                )

        session.commit()  # On valide le reste
        print(
            f"✅ Opération terminée : {inserted_count} insérés, {skipped_count} ignorés."
        )

    except SQLAlchemyError as e:
        session.rollback()
        print(f"❌ Erreur lors de la sauvegarde : {e}")
    finally:
        session.close()


# =====================================================================
# --- BLOC D'EXÉCUTION PRINCIPAL (LE COUP D'ÉCLAIR ⚡) ---
# =====================================================================
if __name__ == "__main__":
    print("🦇 Réveil de l'architecture Supabase...")

    init_db()

    fichier_donnees = PARQUET_FILE_PATH

    if os.path.exists(fichier_donnees):
        print(f"📖 Lecture du grimoire de données : {fichier_donnees}")
        df_final = pl.read_parquet(fichier_donnees)
        lignes_a_inserer = df_final.to_dicts()
        save_to_supabase(lignes_a_inserer)
    else:
        print(f"⚠️ Le fichier '{fichier_donnees}' est introuvable.")
