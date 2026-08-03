# HorRAGore — Contexte de reprise pour Claude

## C'est quoi ce projet

Bot conversationnel spécialisé dans le cinéma d'horreur. Architecture **Multi-Agent peer-to-peer** sous LangGraph : RAG local → Scraper web conditionnel → Narration → Juge. Objectif : **zéro hallucination**.

Projet de formation (DEV IA, Antony Schutz).

---

## Stack exact

- **Python** : géré via `uv`
- **LLM raisonnement/narration** : `llama3.1` (8B) via Ollama
- **LLM embeddings** : `nomic-embed-text` via Ollama
- **Base de données** : Supabase (PostgreSQL + pgvector)
- **Cache vectoriel** : FAISS (`faiss_index.bin` en RAM)
- **Orchestration** : LangGraph + LangChain
- **Observabilité** : Langfuse (3000) + Prometheus (9091) + Grafana (3001) + Uptime Kuma (3002)
- **Backend** : FastAPI + Uvicorn (8000)
- **Frontend** : Streamlit (8501)
- **Données** : `data/horragor_enriched.parquet` (10 033 films, 25 colonnes)
- **CI** : GitHub Actions (tests + lint + sphinx → GitHub Pages)
- **CD** : GitHub Actions (build + push Docker Hub + GHCR)
- **Images Docker** : `annavitry/horragor-api:latest` + `annavitry/horragor-frontend:latest`
- **GHCR** : `ghcr.io/annavitry/horragor-api:latest` + `ghcr.io/annavitry/horragor-frontend:latest`
- **Doc** : https://annavitry.github.io/HorRAGore_3/ (thème Furo)

---

## État actuel

### ✅ Complété
- Pipeline complet fonctionnel (RAG → Scraper → Narration → Juge)
- `_resolve_media` : résolution déterministe du bon film
- `query_movie_metadata` expose director, cast_top5, genres, runtime, tagline depuis Supabase
- CoT mis à jour : réalisateur/casting disponibles en local
- Narration/Juge : réalisateur autorisé depuis données locales
- Scraper API REST Wikipédia (sans lib wikipedia)
- Métriques Prometheus sur `/metrics` (4 compteurs)
- Docker Compose 7 services opérationnel
- Grafana dashboard auto-provisionné
- Uptime Kuma 3 sondes (API, Frontend, Langfuse)
- Ollama configuré sur `0.0.0.0` (accessible depuis Docker)
- UFW autorisé sur `172.19.0.0/24:11434`
- 79 tests unitaires (router.py 100%)
- Documentation Sphinx thème Furo sur GitHub Pages
- CI GitHub Actions (tests + lint + sphinx)
- CD GitHub Actions (Docker Hub + GHCR)
- Release v3.0.0
- Issues #1-#6 fermées
- Pull Shark x4 🦈

### ⬜ Reste à faire
- **Refresh tokens / sécurité inter-services** (brief)
- **Tests finaux** : tester toutes les versions (GHCR, Docker Hub, docker compose)
- Retirer les 3 prints `🔍 [RAG DEBUG]` dans `nodes.py`
- Print debug `📄 [SCRAPER] Contenu brut` à retirer aussi

---

## Décisions d'architecture importantes

### `_resolve_media`
Match exact titre (insensible casse) → plus court titre contenant la référence. **Ne pas revenir à l'ancien `ilike().first()`.**

### Vérité-terrain SQL brute
`local_lore` = sortie SQL brute. Le LLM ne sert qu'au routage, jamais à re-formater les faits.

### Coupe-circuit scraper-only
Ne compte que les appels `scrape_detailed_synopsis`, pas les outils RAG.

### Scraper sans lib `wikipedia`
API REST directe (`opensearch` + `summary` + `action=parse`), User-Agent explicite, retry backoff.

### `OLLAMA_BASE_URL`
Variable dans `config.py`, injectée par `docker-compose.yml` avec `http://172.19.0.1:11434`. En local : `http://localhost:11434`.

### web_data / local_lore en texte propre
`"\n\n---\n\n".join(str(w) for w in web_data)` — jamais de liste Python brute dans un prompt.

### Garde-fou déterministe des années
`_detect_fabricated_years` : année absente des sources → rejet forcé.

---

## Ce que Claude NE doit PAS faire

- Ne pas reconstruire la base sans raison (`supabase_db.py` prend du temps)
- Ne pas réintroduire la lib `wikipedia`
- Ne pas changer `local_lore` (doit rester SQL brut)
- Ne pas supprimer `horragor_enriched.parquet`
- Ne pas merger en local (`git merge`) — toujours via PRs GitHub
- Ne pas utiliser `sphinx-rtd-theme` (on utilise **Furo**)

---

## Fichiers clés

| Fichier | Responsabilité |
|---|---|
| `src/config.py` | Chemin parquet, URL Supabase, OLLAMA_BASE_URL |
| `src/tools/rag_tool.py` | `_resolve_media`, SQL + pgvector, colonnes TMDB |
| `src/tools/scraper_tool.py` | API REST Wikipédia, `_pick_best_result`, `_extract_content` |
| `src/graph/nodes.py` | 4 agents + `_detect_fabricated_years` + prints DEBUG à retirer |
| `src/graph/router.py` | Coupe-circuit scraper-only, aiguillage |
| `src/main.py` | FastAPI + middleware Prometheus + `/metrics` |
| `supabase_db.py` | ETL avec colonnes TMDB, `_safe_str(max_len=)` |
| `docker-compose.yml` | 7 services, images Docker Hub, `OLLAMA_BASE_URL=172.19.0.1` |
| `.github/workflows/ci.yml` | Tests + lint + Sphinx + deploy GitHub Pages (Furo) |
| `.github/workflows/cd.yml` | Build + push Docker Hub + GHCR (`env.OWNER=annavitry`) |
| `docs/conf.py` | Sphinx config, thème Furo |
| `tests/` | 79 tests unitaires, `conftest.py` mocke les env vars |

---

## Prochaine session — dans l'ordre

1. **Retirer les prints DEBUG** dans `nodes.py` (🔍 RAG DEBUG + 📄 SCRAPER)
2. **Sécurité inter-services** (refresh tokens) — dernière exigence du brief
3. **Tests finaux** : GHCR, Docker Hub, `docker compose up -d` from scratch
4. **Merge final** sur main propre avant soutenance