import os
from datetime import date

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
    text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.config import PARQUET_FILE_PATH, SUPABASE_URL

Base = declarative_base()

# =====================================================================
# --- STRUCTURE 3NF (Modèle Physique de Données) ---
# =====================================================================


class Media(Base):
    __tablename__ = "medias"
    id = Column(Integer, primary_key=True)
    horragor_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    release_date = Column(Date)
    category = Column(String(50))

    # --- Financier (parquet original) ---
    budget = Column(BigInteger, default=0)
    revenue = Column(BigInteger, default=0)

    # --- Enrichissement TMDB ---
    director = Column(String(500))  # ex: "Ridley Scott"
    cast_top5 = Column(String(1000))  # ex: "Tom Skerritt, Sigourney Weaver, ..."
    genres = Column(String(255))  # ex: "Horror, Science Fiction"
    runtime = Column(Integer)  # durée en minutes
    tagline = Column(Text)  # ex: "In space no one can hear you scream"
    original_language = Column(String(10))  # ex: "en"
    budget_tmdb = Column(BigInteger)  # budget réel TMDB (None = non renseigné)
    revenue_tmdb = Column(BigInteger)  # recettes TMDB
    tmdb_vote_count = Column(Integer)  # nb votes TMDB

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
# --- MOTEUR ---
# =====================================================================
engine = create_engine(SUPABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# =====================================================================
# --- INITIALISATION DU SCHÉMA ---
# =====================================================================
def init_db():
    print("🗄️ Initialisation du MPD (Modèle Physique de Données)...")
    print("🧨 Nettoyage absolu en cours (Drop CASCADE)...")
    with engine.begin() as conn:
        conn.execute(
            text(
                "DROP TABLE IF EXISTS movie_info, book_info, content_store, scores, medias CASCADE;"
            )
        )

    print(
        "🏗️ Reconstruction des tables avec le nouveau schéma (colonnes TMDB incluses)..."
    )
    Base.metadata.create_all(bind=engine)

    print("🛡️ Sécurisation de l'API Supabase (Activation RLS et Politiques)...")
    tables = ["medias", "scores", "book_info", "content_store"]
    with engine.begin() as conn:
        for t in tables:
            conn.execute(text(f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY;"))
            conn.execute(
                text(
                    f'CREATE POLICY "Lecture publique {t}" ON public.{t} FOR SELECT TO public USING (true);'
                )
            )
    print("🔒 La base est désormais sécurisée en lecture seule pour l'API.")


# =====================================================================
# --- INGESTION ---
# =====================================================================
def _safe_int(val) -> int | None:
    """Convertit une valeur en int, renvoie None si vide/nul/0."""
    try:
        v = int(val)
        return v if v != 0 else None
    except (TypeError, ValueError):
        return None


def _safe_str(val) -> str | None:
    """Renvoie None si la valeur est vide, NaN ou nulle."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ("nan", "none", "") else None


def save_to_supabase(records: list[dict]) -> None:
    session = SessionLocal()
    print(f"💾 Insertion massive OPTIMISÉE (Batch) de {len(records)} entités...")

    enriched_cols = {
        "director",
        "cast_top5",
        "genres",
        "runtime",
        "tagline",
        "original_language",
        "budget_tmdb",
        "revenue_tmdb",
        "tmdb_vote_count",
    }
    has_enrichment = any(k in records[0] for k in enriched_cols) if records else False

    if has_enrichment:
        print("   ✨ Colonnes TMDB détectées dans le parquet — enrichissement activé.")
    else:
        print(
            "   ℹ️  Pas de colonnes TMDB dans le parquet (parquet original). Ingestion standard."
        )

    try:
        print("⏳ Vérification de l'idempotence (1 seule requête réseau)...")
        existing_ids = {row[0] for row in session.query(Media.horragor_id).all()}

        inserted = 0
        skipped = 0

        for rec in records:
            if not rec.get("horragor_id"):
                continue
            if rec["horragor_id"] in existing_ids:
                skipped += 1
                continue

            # --- Date ---
            dt = None
            if rec.get("release_date"):
                try:
                    dt = date.fromisoformat(str(rec["release_date"]))
                except ValueError:
                    dt = None

            new_media = Media(
                horragor_id=rec["horragor_id"],
                title=rec["title"],
                release_date=dt,
                category=rec.get("source_universe", "Inconnu"),
                # Financier original (parquet de base)
                budget=_safe_int(rec.get("budget")) or 0,
                revenue=_safe_int(rec.get("revenue")) or 0,
                # Enrichissement TMDB (None si absent du parquet)
                director=_safe_str(rec.get("director")),
                cast_top5=_safe_str(rec.get("cast_top5")),
                genres=_safe_str(rec.get("genres")),
                runtime=_safe_int(rec.get("runtime")),
                tagline=_safe_str(rec.get("tagline")),
                original_language=_safe_str(rec.get("original_language")),
                budget_tmdb=_safe_int(rec.get("budget_tmdb")),
                revenue_tmdb=_safe_int(rec.get("revenue_tmdb")),
                tmdb_vote_count=_safe_int(rec.get("tmdb_vote_count")),
            )
            session.add(new_media)
            session.flush()

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

            inserted += 1
            if inserted % 1000 == 0:
                session.commit()
                print(f"   🚀 [Batch] {inserted} films expédiés et validés en base...")

        session.commit()
        print(f"✅ Opération terminée : {inserted} insérés, {skipped} ignorés.")

    except SQLAlchemyError as e:
        session.rollback()
        print(f"❌ Erreur lors de la sauvegarde : {e}")
    finally:
        session.close()


# =====================================================================
# --- BLOC PRINCIPAL ---
# =====================================================================
if __name__ == "__main__":
    print("🦇 Réveil de l'architecture Supabase...")

    init_db()

    if os.path.exists(PARQUET_FILE_PATH):
        label = "enrichi" if "enriched" in PARQUET_FILE_PATH else "original"
        print(f"📖 Lecture du grimoire de données ({label}) : {PARQUET_FILE_PATH}")
        df = pl.read_parquet(PARQUET_FILE_PATH)
        save_to_supabase(df.to_dicts())
    else:
        print(f"⚠️ Le fichier '{PARQUET_FILE_PATH}' est introuvable.")
