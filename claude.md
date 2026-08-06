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
- **CD** : GitHub Actions (Docker Hub + GHCR)
- **Images Docker** : `annavitry/horragor-api:latest` + `annavitry/horragor-frontend:latest`
- **GHCR** : `ghcr.io/annavitry/horragor-api:latest` + `ghcr.io/annavitry/horragor-frontend:latest`
- **Doc** : https://annavitry.github.io/HorRAGore_3/ (thème Furo)

---

## État actuel

### ✅ Complété
- Pipeline complet fonctionnel (RAG → Scraper → Narration → Juge)
- `_resolve_media` : résolution déterministe du bon film
- `query_movie_metadata` expose director, cast_top5, genres, runtime, tagline
- Scraper API REST Wikipédia (sans lib wikipedia)
- Métriques Prometheus sur `/metrics`
- Docker Compose 7 services opérationnel
- Grafana dashboard auto-provisionné
- Uptime Kuma 3 sondes
- Ollama sur `0.0.0.0` + UFW `172.19.0.0/24:11434`
- 79 tests unitaires (router.py 100%)
- Documentation Sphinx thème Furo sur GitHub Pages
- CI/CD GitHub Actions (Docker Hub + GHCR)
- Release v3.0.0
- Pull Shark x5 🦈
- Wiki GitHub (5 pages)
- `start.sh` script de démarrage
- Liens services dans la sidebar Streamlit
- Sécurité API Key inter-services (`X-API-Key`)

### ⚠️ Bug connu à régler en priorité
- **HTTP 401 sur /chat** : les images Docker Hub/GHCR sont l'ancienne version
  sans `_API_HEADERS` dans `frontend/app.py`. Le CD doit rebuilder les images
  après le dernier commit (feat/security). Relancer le CD ou faire un push
  vide sur main pour déclencher le rebuild.

### ⬜ Reste à faire
- **Attendre rebuild CD** puis retester Docker Hub + GHCR
- **Test GHCR** : modifier docker-compose.yml → `ghcr.io/annavitry/horragor-*`
- **Test from scratch** : `docker compose down -v && docker compose up -d`

---

## Décisions d'architecture importantes

### `_resolve_media`
Match exact titre → plus court titre. **Ne pas revenir à `ilike().first()`.**

### Vérité-terrain SQL brute
`local_lore` = sortie SQL brute. LLM sert uniquement au routage.

### Coupe-circuit scraper-only
Ne compte que `scrape_detailed_synopsis`, pas les outils RAG.

### Scraper sans lib `wikipedia`
API REST directe, User-Agent explicite, retry backoff.

### `OLLAMA_BASE_URL`
`config.py` + `docker-compose.yml` → `http://172.19.0.1:11434`.

### Sécurité inter-services
`verify_api_key` dans `main.py` vérifie header `X-API-Key`.
`API_SECRET_KEY` vide = mode dev (accès libre).
Frontend envoie `_API_HEADERS = {"X-API-Key": _API_SECRET_KEY}`.

---

## Ce que Claude NE doit PAS faire

- Ne pas reconstruire la base sans raison
- Ne pas réintroduire la lib `wikipedia`
- Ne pas changer `local_lore`
- Ne pas supprimer `horragor_enriched.parquet`
- Ne pas merger en local — toujours via PRs GitHub
- Ne pas utiliser `sphinx-rtd-theme` (on utilise Furo)

---

## Fichiers clés

| Fichier | Responsabilité |
|---|---|
| `src/config.py` | Chemin parquet, URL Supabase, OLLAMA_BASE_URL |
| `src/tools/rag_tool.py` | `_resolve_media`, SQL + pgvector, colonnes TMDB |
| `src/tools/scraper_tool.py` | API REST Wikipédia |
| `src/graph/nodes.py` | 4 agents + garde-fous déterministes |
| `src/graph/router.py` | Coupe-circuit scraper-only, aiguillage |
| `src/main.py` | FastAPI + Prometheus + `verify_api_key` |
| `supabase_db.py` | ETL avec colonnes TMDB |
| `docker-compose.yml` | 7 services, images Docker Hub, OLLAMA_BASE_URL, API_SECRET_KEY |
| `.github/workflows/ci.yml` | Tests + lint + Sphinx + GitHub Pages (Furo) |
| `.github/workflows/cd.yml` | Build + push Docker Hub + GHCR |
| `start.sh` | Script démarrage : docker compose + ouverture navigateur |
| `docs/conf.py` | Sphinx config, thème Furo |
| `tests/` | 79 tests unitaires |

---

## Prochaine session — dans l'ordre

1. **Vérifier que le CD a rebuildé** les images après feat/security merge
2. **Tester Docker Hub** : `docker compose up -d` → chat → Ridley Scott ✅
3. **Tester GHCR** : remplacer images par `ghcr.io/annavitry/horragor-*`
4. **Test from scratch** : `docker compose down -v && docker compose up -d`
5. **Merge final** propre avant soutenance