# HorRAGore — Contexte de reprise pour Claude

## C'est quoi ce projet

Bot conversationnel spécialisé dans le cinéma d'horreur. Architecture **Multi-Agent peer-to-peer** sous LangGraph (pas de manager central) : RAG local → Scraper web conditionnel → Narration → Juge. Objectif affiché dans le README : **zéro hallucination**.

Projet de formation (DEV IA, Antony Schutz). Le cahier des charges demandait 3 agents + Langfuse. On a livré les 3 agents conformes + des couches défensives supplémentaires (garde-fous déterministes, fact-check Juge, résolution film).

---

## Stack exact

- **Python** : géré via `uv` (pas pip, pas poetry)
- **LLM local raisonnement/narration** : `llama3.1` (8B) via Ollama
- **LLM local embeddings** : `nomic-embed-text` via Ollama
- **Base de données** : Supabase (PostgreSQL + pgvector)
- **Cache vectoriel** : FAISS (`faiss_index.bin` en RAM au démarrage)
- **Orchestration** : LangGraph + LangChain
- **Observabilité** : Langfuse (Docker local, port 3000)
- **Backend** : FastAPI + Uvicorn
- **Frontend** : Streamlit (`frontend/app.py`)
- **Données** : `data/horragor_enriched.parquet` (10 033 films, 25 colonnes)

---

## Données

**Source unique** : `data/horragor_enriched.parquet` (ne pas supprimer, ne pas remplacer par l'original).

Enrichi via API TMDB — colonnes ajoutées : `director`, `cast_top5`, `genres`, `runtime`, `tagline`, `original_language`, `budget_tmdb`, `revenue_tmdb`, `tmdb_vote_count`.

Taux de remplissage des colonnes clés :
- `director` : 93.9% (9421/10033)
- `cast_top5` : 93.9%
- `genres` : 95.3%
- `runtime` : 91.2%
- `budget_tmdb` : 20.6% (beaucoup de films indépendants non renseignés)

**Ce qui n'existe PAS dans les données** : la colonne `budget` originale est à 0 sur 100% des lignes — seul `budget_tmdb` est fiable.

---

## Décisions d'architecture importantes

### `_resolve_media` (rag_tool.py)
Résolution déterministe du film : match exact du titre (insensible à la casse) en priorité, puis plus court titre contenant la référence. Remplace l'ancien `ilike('%ref%').first()` qui renvoyait le premier film physique (ex: « Alienation » au lieu du vrai « Alien »). **Ne pas revenir à l'ancien comportement.**

### Vérité-terrain SQL brute (nodes.py → rag_node)
`local_lore` contient la **sortie SQL brute** des outils, pas une ré-extraction LLM. L'ancien extracteur `RagHarvest` déformait les dates (1979 → 2024). Le LLM ne sert qu'à décider du routage (`is_database_sufficient`), jamais à re-formater les faits.

### Coupe-circuit scraper-only (router.py)
`route_after_tools` ne compte que les appels `scrape_detailed_synopsis`, pas les outils RAG. L'ancien compteur global déclenchait le coupe-circuit dès 4 appels (RAG en faisait 3 + scraper 1 = coupure avant que le résultat arrive).

### Scraper sans lib `wikipedia` (scraper_tool.py)
La lib `wikipedia` était trop fragile (User-Agent générique rate-limité, JSONDecodeError opaques). Remplacée par des appels directs à l'API REST Wikipédia (`opensearch` + `/api/rest_v1/page/summary/` + `action=parse`) avec User-Agent explicite et retry backoff. **Ne pas réintroduire la lib `wikipedia`.**

### Intro Wikipédia toujours incluse
`_extract_content` inclut systématiquement le résumé introductif de la page (qui contient réalisateur + acteurs dès la première phrase) avant les sections Production. L'ancienne version ne l'incluait qu'en fallback → Ridley Scott manquait dans le butin.

### Fallback déterministe du scraper (nodes.py → scraper_node)
Si le LLM 8B n'émet pas le `tool_call`, le scraper est forcé via `_extract_title_from_facts` sur le SQL brut. Évite le no-op silencieux.

### web_data et local_lore formatés en texte (nodes.py)
`web_data` est une liste Python. Un f-string `{web_data}` affiche `['...']` avec crochets — le 8B ne lit pas dedans. On joint proprement : `"\n\n---\n\n".join(str(w) for w in web_data)`. **Toujours formatter en texte avant injection dans un prompt.**

### Réalisateur/casting = données web uniquement (pour l'instant)
Les prompts Narration et Juge interdisent de citer un réalisateur absent des données web. Cette règle devra être mise à jour quand `rag_tool.py` exposera `director` depuis Supabase (voir Prochaine étape).

### Garde-fou déterministe des années (nodes.py → quality_control_node)
`_detect_fabricated_years` extrait toutes les années (regex `1[89]\d{2}|20\d{2}`) de la narration et les compare aux sources. Une année absente des sources → rejet forcé, indépendamment du verdict LLM.

---

## Ce que Claude NE doit PAS faire

- **Ne pas reconstruire la base** (`supabase_db.py`) sans raison explicite — ça prend du temps et efface les données.
- **Ne pas réintroduire `patch_tmdb_columns.py` ou `enrich_parquet.py`** — retirés du repo, le parquet enrichi est la source définitive.
- **Ne pas réintroduire la lib `wikipedia`**.
- **Ne pas changer `local_lore`** pour y mettre autre chose que le SQL brut.
- **Ne pas supprimer `horragor_enriched.parquet`** — l'original a été supprimé.
- **Ne pas ajouter `TMDB_API_KEY` au runtime** — plus utilisée dans le code.

---

## Fichiers clés

| Fichier | Responsabilité réelle |
|---|---|
| `src/config.py` | Chemin absolu vers le parquet enrichi, URL Supabase, noms des modèles |
| `src/tools/rag_tool.py` | `_resolve_media`, `query_movie_metadata` (SQL), `find_similar_horror_movies` (pgvector) |
| `src/tools/scraper_tool.py` | API REST Wikipédia, `_pick_best_result`, `_extract_content` avec intro en tête |
| `src/graph/nodes.py` | 4 agents + helpers `_detect_fabricated_years`, `_extract_title_from_facts` |
| `src/graph/router.py` | Coupe-circuit scraper-only, aiguillage conditionnel |
| `src/graph/pipeline.py` | Câblage LangGraph, compilation du graphe |
| `supabase_db.py` | ETL : DROP CASCADE + reconstruction schéma + ingestion parquet enrichi |
| `src/models/state.py` | `AgentState`, `EvaluationVerdict` (Pydantic) |

---

## Problèmes connus et limitations assumées

- **Juge LLM imparfait** : le fact-check LLM rate parfois des hallucinations. Le garde-fou déterministe des années compense partiellement.
- **Budget faiblement renseigné** : `budget_tmdb` à 20.6%. Assumé honnêtement par la Narration.
- **Scraper réseau-dépendant** : si Wikipédia est inaccessible après les retries, la Narration dit « archives muettes ».
- **`is_database_sufficient`** : CoT sous llama3.1, pas parfait. Peut mal router dans les cas ambigus.

---

## État au moment de cette écriture

- ✅ Pipeline complet fonctionnel (RAG → Scraper → Narration → Juge)
- ✅ Résolution film correcte (`_resolve_media`)
- ✅ Scraper API REST opérationnel (Ridley Scott récupéré depuis Wikipédia)
- ✅ Zéro hallucination sur les cas testés (Alien 1979)
- ✅ Base Supabase avec colonnes TMDB patchées (9421 réalisateurs)
- ✅ Parquet enrichi en place (`horragor_enriched.parquet`, 25 colonnes)
- ⬜ `rag_tool.py` pas encore mis à jour pour exposer `director`/`cast_top5` depuis Supabase
- ⬜ Prompts Narration/Juge pas encore mis à jour pour autoriser le réalisateur depuis la base locale

---

## Prochaine étape logique

Mettre à jour `query_movie_metadata` dans `rag_tool.py` pour exposer `director`, `cast_top5`, `genres`, `runtime` depuis Supabase. Une question « qui a réalisé Alien ? » pourrait alors être répondue en local sans scraper. Implique aussi de mettre à jour :
1. Le CoT de `is_database_sufficient` → le réalisateur est maintenant disponible localement
2. La règle 2 de la Narration → autoriser le réalisateur depuis les données locales
3. La règle 2 du Juge → vérifier le réalisateur contre les sources locales ET web