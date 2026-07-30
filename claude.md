# HorRAGore — Contexte de reprise pour Claude

## C'est quoi ce projet

Bot conversationnel spécialisé dans le cinéma d'horreur. Architecture **Multi-Agent peer-to-peer** sous LangGraph (pas de manager central) : RAG local → Scraper web conditionnel → Narration → Juge. Objectif affiché dans le README : **zéro hallucination**.

Projet de formation (DEV IA, Antony Schutz). Le cahier des charges demandait 3 agents + Langfuse. On a livré les 3 agents conformes + des couches défensives supplémentaires + infrastructure Docker d'observabilité.

---

## Stack exact

- **Python** : géré via `uv` (pas pip, pas poetry)
- **LLM local raisonnement/narration** : `llama3.1` (8B) via Ollama
- **LLM local embeddings** : `nomic-embed-text` via Ollama
- **Base de données** : Supabase (PostgreSQL + pgvector)
- **Cache vectoriel** : FAISS (`faiss_index.bin` en RAM au démarrage)
- **Orchestration** : LangGraph + LangChain
- **Observabilité** : Langfuse (port 3000) + Prometheus (9090) + Grafana (3001) + Uptime Kuma (3002)
- **Backend** : FastAPI + Uvicorn (port 8000)
- **Frontend** : Streamlit (`frontend/app.py`, port 8501)
- **Données** : `data/horragor_enriched.parquet` (10 033 films, 25 colonnes)

---

## Données

**Source unique** : `data/horragor_enriched.parquet` (ne pas supprimer).

Enrichi via API TMDB — colonnes ajoutées : `director`, `cast_top5`, `genres`, `runtime`, `tagline`, `original_language`, `budget_tmdb`, `revenue_tmdb`, `tmdb_vote_count`.

Taux de remplissage : `director` 93.9%, `genres` 95.3%, `runtime` 91.2%, `budget_tmdb` 20.6%.

**Cas particulier Alien** : `tmdb_id = None` dans le parquet source → colonnes TMDB à `None` en base. Le parquet a été patché manuellement avec les données correctes (Ridley Scott, tmdb_id=348). Un nouveau `supabase_db.py` est à relancer pour charger ce parquet corrigé en base.

---

## État actuel du pipeline

- ✅ Pipeline complet fonctionnel (RAG → Scraper → Narration → Juge)
- ✅ `query_movie_metadata` expose `director`, `cast_top5`, `genres`, `runtime`, `tagline` depuis Supabase
- ✅ CoT mis à jour : réalisateur/casting disponibles en local → `is_database_sufficient = True`
- ✅ Narration/Juge : réalisateur autorisé depuis les données locales
- ✅ Scraper fonctionne en fallback (Ridley Scott récupéré depuis Wikipédia quand base vide)
- ✅ Métriques Prometheus exposées sur `/metrics` (`prometheus-client` installé)
- ✅ `docker-compose.yml` créé avec 7 services
- ⚠️  Alien : base Supabase a encore `director=None` — nécessite `supabase_db.py` avec le parquet corrigé
- ⬜ `docker compose up -d` pas encore lancé (à faire demain)
- ⬜ Tests automatiques (80% couverture)
- ⬜ Documentation Sphinx
- ⬜ CI/CD
- ⬜ Refresh tokens / sécurité inter-services
- ⬜ Print debug temporaire à retirer dans `nodes.py` (3 lignes `🔍 [RAG DEBUG]`)

---

## Infrastructure Docker (branche `feat/docker-observability`)

Fichiers créés :
```
docker-compose.yml          ← 7 services en une commande
Dockerfile.api              ← image FastAPI + LangGraph
Dockerfile.frontend         ← image Streamlit
.dockerignore
monitoring/
  prometheus.yml            ← scrape /metrics toutes les 15s
  grafana/provisioning/
    datasources/prometheus.yml   ← Prometheus auto-connecté
    dashboards/dashboards.yml
```

**Ports** :
- 3000 → Langfuse
- 3001 → Grafana (admin/horragor)
- 3002 → Uptime Kuma
- 8000 → API FastAPI
- 8501 → Frontend Streamlit
- 9090 → Prometheus

**Important** : Ollama reste sur la machine hôte (pas dockerisé — GPU). L'API l'atteint via `host.docker.internal:11434` + `extra_hosts: host-gateway`.

**Métriques exposées** (`/metrics`) :
- `horragor_http_requests_total` (Counter, par endpoint + statut)
- `horragor_http_request_duration_seconds` (Histogram, buckets adaptés LLM)
- `horragor_graph_errors_total` (Counter)
- `horragor_chat_success_total` (Counter)

---

## Décisions d'architecture importantes

### `_resolve_media` (rag_tool.py)
Match exact titre (insensible casse) → plus court titre contenant la référence. **Ne pas revenir à l'ancien `ilike().first()`.**

### Vérité-terrain SQL brute (nodes.py → rag_node)
`local_lore` = sortie SQL brute des outils. Le LLM ne sert qu'au routage, jamais à re-formater les faits.

### Coupe-circuit scraper-only (router.py)
Ne compte que les appels `scrape_detailed_synopsis`, pas les outils RAG.

### Scraper sans lib `wikipedia`
API REST directe (`opensearch` + `summary` + `action=parse`), User-Agent explicite, retry backoff.

### web_data / local_lore en texte propre
`"\n\n---\n\n".join(str(w) for w in web_data)` — jamais de liste Python brute dans un prompt.

### Garde-fou déterministe des années
`_detect_fabricated_years` : année absente des sources → rejet forcé indépendamment du Juge LLM.

---

## Ce que Claude NE doit PAS faire

- Ne pas reconstruire la base sans raison (temps + vecteurs effacés)
- Ne pas réintroduire la lib `wikipedia`
- Ne pas changer `local_lore` (doit rester SQL brut)
- Ne pas supprimer `horragor_enriched.parquet`
- Ne pas ajouter `TMDB_API_KEY` au runtime

---

## Fichiers clés

| Fichier | Responsabilité |
|---|---|
| `src/config.py` | Chemin parquet, URL Supabase, noms modèles |
| `src/tools/rag_tool.py` | `_resolve_media`, SQL + pgvector, colonnes TMDB exposées |
| `src/tools/scraper_tool.py` | API REST Wikipédia, `_pick_best_result`, `_extract_content` |
| `src/graph/nodes.py` | 4 agents + `_detect_fabricated_years` + `_extract_title_from_facts` |
| `src/graph/router.py` | Coupe-circuit scraper-only, aiguillage |
| `src/graph/pipeline.py` | Câblage LangGraph |
| `src/main.py` | FastAPI + middleware Prometheus + route `/metrics` |
| `supabase_db.py` | ETL complet avec colonnes TMDB |
| `docker-compose.yml` | 7 services observabilité + app |

---

## Prochaine session — dans l'ordre

1. **Relancer `supabase_db.py`** avec le parquet corrigé (Alien → Ridley Scott en base)
2. **Retirer les 3 prints `🔍 [RAG DEBUG]`** dans `nodes.py`
3. **`docker compose up -d`** et vérifier que les 7 services démarrent
4. Configurer un dashboard Grafana pour la latence `/chat`
5. Vérifier Uptime Kuma surveille bien `http://api:8000/` et `http://frontend:8501/`
6. Tests automatiques (80% couverture) — pytest
7. Documentation Sphinx