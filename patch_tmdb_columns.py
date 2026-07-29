"""Patch SQL : met à jour les colonnes TMDB dans Supabase SANS reconstruire la base.

Aucun DROP, aucun recalcul de vecteurs, aucune perte de données.
Fait uniquement des UPDATE ciblés sur les colonnes nouvelles.

Usage :
    python patch_tmdb_columns.py

Prérequis :
    - data/horragor_enriched.parquet doit exister (enrich_parquet.py terminé)
    - Les colonnes TMDB doivent exister dans la table medias de Supabase.
      Si ce n'est pas le cas (première fois), le script les crée via ALTER TABLE.
"""

import math
from pathlib import Path

import polars as pl
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from src.config import SUPABASE_URL

PARQUET_ENRICHED = Path("data/horragor_enriched.parquet")

# Colonnes TMDB à patcher : (nom_colonne, type_sql)
TMDB_COLUMNS = [
    ("director", "VARCHAR(500)"),
    ("cast_top5", "VARCHAR(1000)"),
    ("genres", "VARCHAR(255)"),
    ("runtime", "INTEGER"),
    ("tagline", "TEXT"),
    ("original_language", "VARCHAR(10)"),
    ("budget_tmdb", "BIGINT"),
    ("revenue_tmdb", "BIGINT"),
    ("tmdb_vote_count", "INTEGER"),
]

from sqlalchemy import create_engine

engine = create_engine(SUPABASE_URL)


def _ensure_columns_exist() -> None:
    """Crée les colonnes TMDB si elles n'existent pas encore dans la table medias."""
    inspector = inspect(engine)
    existing = {col["name"] for col in inspector.get_columns("medias")}
    missing = [(col, typ) for col, typ in TMDB_COLUMNS if col not in existing]

    if not missing:
        print("✅ Toutes les colonnes TMDB existent déjà dans la table medias.")
        return

    print(f"🏗️ Création de {len(missing)} colonne(s) manquante(s) via ALTER TABLE...")
    with engine.begin() as conn:
        for col, typ in missing:
            conn.execute(
                text(f"ALTER TABLE public.medias ADD COLUMN IF NOT EXISTS {col} {typ};")
            )
            print(f"   + {col} ({typ})")
    print("✅ Colonnes créées.")


def _safe_val(val):
    """Renvoie None si la valeur est vide/NaN/0 (pour les entiers financiers)."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    if s.lower() in ("", "none", "nan", "null"):
        return None
    return val


def patch_tmdb(batch_size: int = 500) -> None:
    if not PARQUET_ENRICHED.exists():
        print(f"❌ Fichier introuvable : {PARQUET_ENRICHED}")
        print("   Lance d'abord : python enrich_parquet.py --api-key TON_API_KEY")
        return

    print(f"📖 Lecture du parquet enrichi : {PARQUET_ENRICHED}")
    df = pl.read_parquet(PARQUET_ENRICHED)
    print(f"   {df.height} lignes, {len(df.columns)} colonnes.")

    # Vérifie qu'on a bien les colonnes enrichies
    tmdb_cols_present = [c for c, _ in TMDB_COLUMNS if c in df.columns]
    if not tmdb_cols_present:
        print(
            "❌ Aucune colonne TMDB trouvée dans le parquet. L'enrichissement est-il terminé ?"
        )
        return
    print(f"   Colonnes TMDB présentes : {tmdb_cols_present}")

    # Rapport rapide : combien de lignes ont vraiment été enrichies ?
    if "director" in df.columns:
        enriched_count = df["director"].drop_nulls().len()
        print(f"   Films avec réalisateur renseigné : {enriched_count}/{df.height}")

    # Crée les colonnes si nécessaire
    _ensure_columns_exist()

    # Filtre : seulement les lignes qui ont au moins une colonne TMDB non nulle
    has_data = pl.lit(False)
    for col in tmdb_cols_present:
        has_data = has_data | pl.col(col).is_not_null()
    df_to_patch = df.filter(has_data)
    print(
        f"\n🔧 Lignes à patcher (au moins 1 champ TMDB non nul) : {df_to_patch.height}"
    )

    if df_to_patch.height == 0:
        print("ℹ️  Rien à patcher.")
        return

    # Construction dynamique du SET selon les colonnes présentes
    set_clauses = ", ".join(
        f"{col} = :{col}" for col, _ in TMDB_COLUMNS if col in df.columns
    )
    sql = text(f"""
        UPDATE public.medias
        SET {set_clauses}
        WHERE horragor_id = :horragor_id
    """)

    updated = 0
    skipped = 0
    errors = 0

    print(f"🚀 Patch en cours (batches de {batch_size})...\n")

    with engine.begin() as conn:
        batch_params = []

        for i, row in enumerate(df_to_patch.iter_rows(named=True)):
            params = {"horragor_id": row["horragor_id"]}
            for col, _ in TMDB_COLUMNS:
                if col in row:
                    params[col] = _safe_val(row[col])
                else:
                    params[col] = None

            # Ne patche que si au moins un champ TMDB est non nul
            has_value = any(params.get(col) is not None for col, _ in TMDB_COLUMNS)
            if not has_value:
                skipped += 1
                continue

            batch_params.append(params)

            if len(batch_params) >= batch_size:
                try:
                    for p in batch_params:
                        conn.execute(sql, p)
                    updated += len(batch_params)
                    print(
                        f"   [{updated:5}/{df_to_patch.height}] {updated / df_to_patch.height * 100:4.1f}% patchés..."
                    )
                except SQLAlchemyError as e:
                    errors += len(batch_params)
                    print(f"   ❌ Erreur batch : {e}")
                batch_params = []

        # Dernier batch
        if batch_params:
            try:
                for p in batch_params:
                    conn.execute(sql, p)
                updated += len(batch_params)
            except SQLAlchemyError as e:
                errors += len(batch_params)
                print(f"   ❌ Erreur dernier batch : {e}")

    print("\n=== RAPPORT PATCH ===")
    print(f"  ✅ Mis à jour : {updated}")
    print(f"  ⏭️  Ignorés (vides) : {skipped}")
    print(f"  ❌ Erreurs : {errors}")
    print("\n🎉 Patch terminé. Lance 'python supabase_db.py' uniquement si tu veux")
    print("   reconstruire la base complète avec le nouveau schéma (vecteurs inclus).")


if __name__ == "__main__":
    patch_tmdb()
