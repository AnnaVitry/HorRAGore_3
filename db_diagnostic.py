"""Diagnostic de synchronisation base Supabase <-> parquet.

À lancer depuis la RACINE du projet, dans ton venv (celui qui a accès à Supabase) :
    python db_diagnostic.py

Objectif : vérifier si le vrai 'Alien' (1979) est réellement en base, ou si
l'import est partiel (ce qui expliquerait la résolution vers 'Alien Love').
"""

from sqlalchemy import func

from src.tools.rag_tool import SessionLocal, _resolve_media
from supabase_db import Media

session = SessionLocal()

try:
    total = session.query(Media).count()
    print(f"📊 Total films en base : {total}   (le parquet du repo en a 10033)")
    if total < 10033:
        print("   ⚠️  Base INCOMPLÈTE -> import partiel probable. C'est la cause.")

    exact = session.query(Media).filter(func.lower(Media.title) == "alien").first()
    print(
        "\n🎯 'Alien' (exact) en base ? -> "
        + (f"PRÉSENT ({exact.release_date})" if exact else "ABSENT  <-- le problème")
    )

    print("\n🔎 Tous les titres contenant 'alien' en base (triés par longueur) :")
    rows = (
        session.query(Media)
        .filter(Media.title.ilike("%alien%"))
        .order_by(func.length(Media.title).asc())
        .all()
    )
    for m in rows[:15]:
        print(f"   - {m.title!r:24} ({m.release_date})")
    print(f"   ... {len(rows)} titres 'alien' au total en base (le parquet en a 161)")

    resolved = _resolve_media(session, "Alien")
    print(
        f"\n🧭 _resolve_media('Alien') renvoie -> "
        f"{resolved.title if resolved else None} "
        f"({resolved.release_date if resolved else '-'})"
    )
    print(
        "\nVerdict : si 'Alien' est ABSENT ou si le total < 10033, "
        "recharge la base avec :  python supabase_db.py"
    )
finally:
    session.close()
