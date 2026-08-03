Schéma de Base de Données
==========================

HorRAGore utilise Supabase (PostgreSQL + pgvector) avec un schéma 3NF.

Modèle Physique de Données
---------------------------

.. code-block:: text

   medias
   ├── id              INTEGER PK
   ├── horragor_id     VARCHAR(100) UNIQUE — identifiant interne
   ├── title           VARCHAR(255)
   ├── release_date    DATE
   ├── category        VARCHAR(50)  — univers (Horreur, Sci-Fi...)
   ├── budget          BIGINT       — budget original (souvent 0)
   ├── revenue         BIGINT
   ├── director        VARCHAR(500) — enrichi via TMDB
   ├── cast_top5       VARCHAR(1000)
   ├── genres          VARCHAR(255)
   ├── runtime         INTEGER      — durée en minutes
   ├── tagline         TEXT
   ├── original_language VARCHAR(10)
   ├── budget_tmdb     BIGINT       — budget réel TMDB
   ├── revenue_tmdb    BIGINT
   └── tmdb_vote_count INTEGER

   scores
   ├── id              INTEGER PK
   ├── media_id        FK → medias.id
   ├── provider        VARCHAR(50)  — "TMDB" ou "RottenTomatoes"
   └── value           FLOAT

   content_store
   ├── id              INTEGER PK
   ├── media_id        FK → medias.id
   ├── synopsis        TEXT
   └── consensus       TEXT         — critique Rotten Tomatoes

   book_info
   ├── id              INTEGER PK
   ├── media_id        FK → medias.id
   └── author          VARCHAR(255)

Extension pgvector
-------------------

La table ``horragor_vectors`` stocke les embeddings des synopsis
(``nomic-embed-text``, dimension 768) pour la recherche de similarité.

Script ETL (supabase_db.py)
----------------------------

.. automodule:: supabase_db
   :members:
   :private-members:
   :undoc-members:
