# 🩸 HorRAGore (Projet de Anna)

[![HorRAGore CI](https://github.com/AnnaVitry/HorRAGore_3/actions/workflows/ci.yml/badge.svg)](https://github.com/AnnaVitry/HorRAGore_3/actions/workflows/ci.yml)
[![HorRAGore CD](https://github.com/AnnaVitry/HorRAGore_3/actions/workflows/cd.yml/badge.svg)](https://github.com/AnnaVitry/HorRAGore_3/actions/workflows/cd.yml)
[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-annavitry-blue?logo=docker)](https://hub.docker.com/u/annavitry)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-green)](https://annavitry.github.io/HorRAGore_3/)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Résumé
HorRAGore est un moteur **RAG (Retrieval-Augmented Generation)** unifié et un pipeline ETL, spécialisé dans l'univers de l'horreur (cinéma, littérature, sci-fi).

Il repose sur une architecture **Multi-Agent (LangGraph)** tolérante aux pannes. Le système interroge une base de données relationnelle et vectorielle, bascule sur une recherche web (Wikipédia) si le savoir local est insuffisant, et soumet la rédaction finale à un Juge IA. L'objectif : générer des récits horrifiques, cyniques et **garantis sans hallucinations**.

---

## 🏗️ Architecture du Projet

```text
HorRAGore_3/
│
├── .env                          # Variables d'environnement (Supabase, Langfuse)
├── example.env                   # Template documenté avec instructions par variable
├── pyproject.toml / uv.lock      # Dépendances via 'uv'
├── supabase_db.py                # Script ETL : reconstruit les tables et insère les données
│
├── docker-compose.yml            # 7 services en une commande (API, Frontend, Langfuse,
│                                 # Prometheus, Grafana, Uptime Kuma, PostgreSQL Langfuse)
├── Dockerfile.api                # Image FastAPI + LangGraph
├── Dockerfile.frontend           # Image Streamlit
├── monitoring/
│   ├── prometheus.yml            # Config scrape Prometheus (toutes les 15s)
│   └── grafana/provisioning/     # Datasource Prometheus + dashboard HorRAGore auto-provisionnés
│
├── data/
│   ├── horragor_enriched.parquet # Dataset enrichi TMDB (10 033 films, 25 colonnes)
│   └── faiss_index.bin           # Cache vectoriel local (généré automatiquement)
│
├── src/
│   ├── main.py                   # FastAPI + middleware Prometheus (/metrics)
│   ├── config.py                 # Source de vérité : chemins, URLs, OLLAMA_BASE_URL
│   ├── graph/
│   │   ├── nodes.py              # 4 Agents (RAG, Scraper, Narration, Juge)
│   │   ├── router.py             # Aiguillage conditionnel, coupe-circuit scraper
│   │   └── pipeline.py           # Câblage LangGraph
│   └── tools/
│       ├── rag_tool.py           # _resolve_media, SQL/PGVector, colonnes TMDB
│       └── scraper_tool.py       # API REST Wikipédia directe (sans lib wikipedia)
│
└── frontend/
    ├── app.py                    # Interface Streamlit (API_URL dynamique)
    └── assets/
        ├── fonts/Ghost_Shadow.ttf
        └── img/damonvampface.png
```

---

## 🤖 Le Moteur Multi-Agent

Orchestration **peer-to-peer** sous LangGraph (pas de manager central) :

1. **Agent RAG** — Interroge Supabase via `_resolve_media` (match exact → plus court titre). Évalue la couverture via Chain-of-Thought. Transmet la vérité-terrain SQL brute à la Narration et au Juge.

2. **Agent Scraper** — Fallback si le local est insuffisant. API REST Wikipédia directe, retry backoff, sélection déterministe du bon article, intro toujours incluse. Fallback déterministe si le LLM n'émet pas le `tool_call`.

3. **Agent Narration** — Fidélité absolue aux données. Champs absents déclarés avec mépris. Réalisateur/casting cités directement depuis Supabase (colonnes TMDB enrichies).

4. **Agent Juge** — Fact-check contre les sources SQL + web. Garde-fou déterministe sur les années hallucinées. Coupe-circuit à 2 refus.

---

## ⚙️ Stack Technique

| Composant | Technologie |
|---|---|
| Gestionnaire de paquets | `uv` |
| LLM Raisonnement/Narration | `llama3.1` (8B) via Ollama |
| LLM Embeddings | `nomic-embed-text` via Ollama |
| Base de données | Supabase (PostgreSQL + pgvector) |
| Cache vectoriel | FAISS |
| Orchestration | LangGraph + LangChain |
| Observabilité | Langfuse + Prometheus + Grafana + Uptime Kuma |
| Backend / Frontend | FastAPI + Uvicorn + Streamlit |
| Infrastructure | Docker Compose (7 services) |

---

## 🚀 Installation et Prérequis

### 1. Prérequis Système

* **Python 3.10+**, **`uv`**, **Docker & Docker Compose**, **Ollama**

### 2. Modèles Ollama

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

### 3. Configuration Ollama pour Docker (Linux)

Par défaut Ollama écoute sur `127.0.0.1` — inaccessible depuis Docker. À faire une seule fois :

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d/
sudo tee /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
EOF
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

Puis autoriser le réseau Docker dans le firewall :

```bash
sudo ufw allow from 172.19.0.0/24 to any port 11434
```

> ℹ️ L'IP `172.19.0.1` est le gateway du réseau Docker HorRAGore. Si elle diffère sur ta machine, mets à jour `OLLAMA_BASE_URL` dans `docker-compose.yml`.

### 4. Environnement Python (dev local uniquement)

```bash
uv venv && source .venv/bin/activate && uv sync
```

### 5. Configuration `.env`

```bash
cp example.env .env
```

```env
SUPABASE_URL="postgresql://postgres.[id]:[mdp]@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="http://localhost:3000"   # dev local
# En Docker, LANGFUSE_HOST est surchargé automatiquement par docker-compose.yml

# Clé API inter-services Frontend → API (génère avec : python3 -c "import secrets; print(secrets.token_urlsafe(32))")
# Laisser vide pour désactiver (mode dev local)
API_SECRET_KEY=""
```

> ⚠️ Ne commite **jamais** le `.env`.

---

## 🏁 Démarrage

### Mode Docker (recommandé)

```bash
# Lance les 7 services en une commande
docker compose up -d
```

| Service | URL | Credentials |
|---|---|---|
| Frontend Streamlit | http://localhost:8501 | — |
| API FastAPI | http://localhost:8000 | — |
| Langfuse | http://localhost:3000 | Créer un compte au 1er accès |
| Grafana | http://localhost:3001 | admin / horragor |
| Prometheus | http://localhost:9091 | — |
| Uptime Kuma | http://localhost:3002 | Créer un compte au 1er accès |

> **Langfuse** : après création du compte, récupère les clés API et ajoute-les dans `.env`.

> **Alternative GHCR** : remplace les images par `ghcr.io/annavitry/horragor-*:latest`

### Mode développement local

```bash
# Étape 1 : Ingestion des données
uv run python supabase_db.py

# Étape 2 : Backend
uv run uvicorn src.main:app --reload

# Étape 3 : Frontend
uv run streamlit run frontend/app.py
```

---

## 🗂️ Gestion du Parquet

| Fichier | Rôle |
|---|---|
| `horragor_enriched.parquet` | Source de vérité unique (25 colonnes : title, director, cast_top5, genres, runtime, budget_tmdb…) |

À conserver précieusement — il est la source de toute reconstruction de la base.

---

## 📊 Observabilité

Métriques exposées sur `/metrics` (scrapées par Prometheus toutes les 15s) :

| Métrique | Type | Description |
|---|---|---|
| `horragor_http_requests_total` | Counter | Requêtes par endpoint + statut |
| `horragor_http_request_duration_seconds` | Histogram | Latence (p50/p95/p99) |
| `horragor_graph_errors_total` | Counter | Erreurs LangGraph |
| `horragor_chat_success_total` | Counter | Réponses chat réussies |

Dashboard Grafana auto-provisionné : **HorRAGore — Observabilité Multi-Agent**.

---

## 🔒 Sécurité Inter-Services

L'endpoint `/chat` est protégé par une clé API partagée entre le Frontend et l'API.

| Header | Valeur | Obligatoire |
|---|---|---|
| `X-API-Key` | Valeur de `API_SECRET_KEY` | Si `API_SECRET_KEY` est définie |

**Génère ta clé :**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Comportement :**
- `API_SECRET_KEY` vide → accès libre (mode dev local)
- `API_SECRET_KEY` définie → `401` sans clé, `403` si clé invalide
- `/` (health check) et `/metrics` (Prometheus) restent publics

---

## 🤝 Contribuer

* Séparation des responsabilités : routage (`router.py`) vs logique métier (`nodes.py`).
* Context Trimming : ne passer à la Narration que les données brutes SQL, jamais les logs.
* **Zéro hallucination** : tout fait exposé doit avoir une source vérifiable. Les champs absents se déclarent, ne s'inventent pas.
* Les gardes-fous déterministes (`_resolve_media`, `_detect_fabricated_years`) doivent rester testables unitairement sans infrastructure.