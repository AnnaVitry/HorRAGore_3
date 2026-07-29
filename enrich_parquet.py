"""Enrichissement du parquet HorRAGor via l'API TMDB.

Usage :
    python enrich_parquet.py --api-key TON_API_KEY_TMDB

Ce que ça fait :
    - Lit data/horragor_final_data.parquet
    - Pour chaque tmdb_id : appelle /movie/{id} (budget, revenue, runtime, tagline...)
      et /movie/{id}/credits (réalisateur, top 5 acteurs)
    - Sauvegarde data/horragor_enriched.parquet (l'original est INCHANGÉ)
    - Affiche un rapport final des colonnes enrichies

Bonnes pratiques API :
    - 40 requêtes / 10s max (limite TMDB gratuit : ~50/s, on est largement en dessous)
    - Retry automatique sur erreur 429 (rate-limit) et 5xx
    - Checkpoint toutes les 500 lignes (reprend où ça s'est arrêté si interruption)
    - Timeout 8s par requête
"""

import argparse
import json
import time
from pathlib import Path

import polars as pl
import requests

# --- Config ---
TMDB_BASE = "https://api.themoviedb.org/3"
PARQUET_IN = Path("data/horragor_final_data.parquet")
PARQUET_OUT = Path("data/horragor_enriched.parquet")
CHECKPOINT = Path("data/.enrich_checkpoint.json")
BATCH_SIZE = 500  # sauvegarde checkpoint toutes les N lignes
SLEEP_BETWEEN = 0.08  # 80ms entre requêtes = ~12 req/s, bien sous la limite
TIMEOUT = 8


def get_session(api_key: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "HorRAGor/3.0 (educational project)",
        }
    )
    # La clé courte (32 car.) s'utilise comme paramètre URL ?api_key=...
    # Le Read Access Token (JWT, ~200 car.) s'utilise en header Bearer.
    # On détecte automatiquement lequel on a.
    if len(api_key) > 50:
        # JWT Read Access Token (v4)
        s.headers["Authorization"] = f"Bearer {api_key}"
        s.params = {}  # type: ignore[attr-defined]
    else:
        # API Key courte (v3) -> paramètre URL
        s.params = {"api_key": api_key}  # type: ignore[attr-defined]
    return s


def fetch_with_retry(session: requests.Session, url: str, retries: int = 3) -> dict:
    """GET avec retry sur 429 (rate-limit) et 5xx."""
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 5))
                print(f"   ⏳ Rate-limit 429, attente {wait}s…")
                time.sleep(wait)
                continue
            if r.status_code in (500, 502, 503):
                time.sleep(2**attempt)
                continue
            if r.status_code == 404:
                return {}  # film inconnu de TMDB, on passe
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                print(f"   ❌ Erreur réseau définitive : {e}")
                return {}
            time.sleep(2**attempt)
    return {}


def fetch_movie(session: requests.Session, tmdb_id: int) -> dict:
    """Récupère métadonnées + crédits pour un film TMDB."""
    meta = fetch_with_retry(session, f"{TMDB_BASE}/movie/{tmdb_id}")
    credits = fetch_with_retry(session, f"{TMDB_BASE}/movie/{tmdb_id}/credits")
    time.sleep(SLEEP_BETWEEN)

    # Réalisateur(s)
    directors = [
        c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"
    ]
    # Top 5 acteurs
    cast = [c["name"] for c in credits.get("cast", [])[:5]]

    return {
        "budget_tmdb": meta.get("budget") or None,  # 0 TMDB = non renseigné -> None
        "revenue_tmdb": meta.get("revenue") or None,
        "runtime": meta.get("runtime") or None,
        "tagline": meta.get("tagline") or None,
        "original_language": meta.get("original_language") or None,
        "genres": ", ".join(g["name"] for g in meta.get("genres", [])) or None,
        "director": ", ".join(directors) or None,
        "cast_top5": ", ".join(cast) or None,
        "tmdb_vote_count": meta.get("vote_count") or None,
    }


def load_checkpoint() -> set[int]:
    """Charge les tmdb_id déjà traités (reprend après interruption)."""
    if CHECKPOINT.exists():
        data = json.loads(CHECKPOINT.read_text())
        print(f"♻️  Checkpoint trouvé : {len(data['done'])} films déjà traités.")
        return set(data["done"])
    return set()


def save_checkpoint(done: set[int]) -> None:
    CHECKPOINT.write_text(json.dumps({"done": list(done)}))


def main(api_key: str) -> None:
    print("📖 Lecture du parquet source…")
    df = pl.read_parquet(PARQUET_IN)
    print(f"   {df.height} films, {len(df.columns)} colonnes.")

    # Colonnes enrichies à créer (initialisées à None)
    new_cols = [
        "budget_tmdb",
        "revenue_tmdb",
        "runtime",
        "tagline",
        "original_language",
        "genres",
        "director",
        "cast_top5",
        "tmdb_vote_count",
    ]

    # Charge ou initialise les résultats enrichis
    if PARQUET_OUT.exists():
        df_out = pl.read_parquet(PARQUET_OUT)
        print(f"   Parquet enrichi existant chargé ({df_out.height} lignes).")
    else:
        # Ajoute les colonnes manquantes avec des nulls
        df_out = df.clone()
        for col in new_cols:
            if col not in df_out.columns:
                df_out = df_out.with_columns(pl.lit(None).cast(pl.Utf8).alias(col))

    done = load_checkpoint()
    session = get_session(api_key)

    rows_data: dict[int, dict] = {}  # tmdb_id -> données enrichies
    total = df.height
    enriched = 0
    skipped_null = 0
    errors = 0

    print(f"\n🚀 Enrichissement de {total} films via TMDB…")
    print("   (Ctrl+C pour interrompre proprement — le checkpoint sera sauvegardé)\n")

    try:
        for i, row in enumerate(df.iter_rows(named=True)):
            tmdb_id = row.get("tmdb_id")

            if not tmdb_id or tmdb_id in done:
                skipped_null += 1
                continue

            data = fetch_movie(session, int(tmdb_id))
            if data:
                rows_data[int(tmdb_id)] = data
                enriched += 1
            else:
                errors += 1

            done.add(int(tmdb_id))

            # Progression
            if (i + 1) % 100 == 0:
                pct = (i + 1) / total * 100
                print(
                    f"   [{i + 1:5}/{total}] {pct:5.1f}% — enrichis={enriched}, erreurs={errors}"
                )

            # Checkpoint intermédiaire
            if (i + 1) % BATCH_SIZE == 0:
                save_checkpoint(done)
                print(f"   💾 Checkpoint sauvegardé ({len(done)} traités).")

    except KeyboardInterrupt:
        print("\n⚠️  Interruption. Sauvegarde du checkpoint…")
        save_checkpoint(done)

    # --- Reconstruction du DataFrame avec les nouvelles données ---
    print(
        f"\n📊 Reconstruction du parquet enrichi ({len(rows_data)} films mis à jour)…"
    )

    # Crée un DataFrame des données enrichies
    if rows_data:
        enriched_rows = [{"tmdb_id": tid, **vals} for tid, vals in rows_data.items()]
        df_enriched = pl.DataFrame(enriched_rows).with_columns(
            pl.col("tmdb_id").cast(pl.Int64)
        )

        # Joint sur tmdb_id
        df_merged = df.join(df_enriched, on="tmdb_id", how="left")
    else:
        df_merged = df.clone()
        for col in new_cols:
            if col not in df_merged.columns:
                df_merged = df_merged.with_columns(
                    pl.lit(None).cast(pl.Utf8).alias(col)
                )

    df_merged.write_parquet(PARQUET_OUT)
    print(f"✅ Parquet enrichi sauvegardé : {PARQUET_OUT}")
    print(f"   Colonnes : {df_merged.columns}")

    # --- Rapport ---
    print("\n=== RAPPORT D'ENRICHISSEMENT ===")
    for col in new_cols:
        if col in df_merged.columns:
            non_null = df_merged[col].drop_nulls().len()
            pct = non_null / df_merged.height * 100
            ex = df_merged[col].drop_nulls().head(2).to_list()
            print(
                f"  {col:22} : {non_null:5}/{df_merged.height} ({pct:4.1f}%) | ex: {ex}"
            )

    print(f"\n  Traités : {len(done)} | Enrichis : {enriched} | Erreurs/404 : {errors}")

    # Nettoyage checkpoint si terminé complètement
    if len(done) >= df.height - skipped_null:
        CHECKPOINT.unlink(missing_ok=True)
        print("  🧹 Checkpoint supprimé (enrichissement complet).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrichit le parquet HorRAGor via TMDB."
    )
    parser.add_argument(
        "--api-key", required=True, help="Ta clé API TMDB (32 caractères)"
    )
    args = parser.parse_args()
    main(args.api_key)
