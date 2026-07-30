# 🩸 HorRAGore (Projet de Anna)

## Résumé
HorRAGore est un moteur **RAG (Retrieval-Augmented Generation)** unifié et un pipeline ETL, spécialisé dans l'univers de l'horreur (cinéma, littérature, sci-fi).

Il repose sur une architecture **Multi-Agent (LangGraph)** tolérante aux pannes. Le système interroge une base de données relationnelle et vectorielle, bascule sur une recherche web (Wikipédia) si le savoir local est insuffisant, et soumet la rédaction finale à un Juge IA. L'objectif : générer des récits horrifiques, cyniques et **garantis sans hallucinations**.

---

## 🏗️ Architecture du Projet

Le projet est divisé en micro-services (Backend / Frontend / Ingestion / Outils).

```text
HorRAGore_3/
│
├── .env                          # Variables d'environnement (Supabase, Langfuse, TMDB)
├── example.env                   # Template documenté avec instructions par variable
├── pyproject.toml / uv.lock      # Fichiers de gestion des dépendances via 'uv'
├── supabase_db.py                # Script ETL : reconstruit les tables et insère les données
│
├── data/                         # Stockage des données locales
│   ├── horragor_enriched.parquet # Dataset source brut (10 033 films d'horreur) enrichi TMDB
│   └── faiss_index.bin           # Cache vectoriel local (généré automatiquement)
│
├── src/                          # 🧠 CŒUR DU BACKEND (FastAPI & LangGraph)
│   ├── main.py                   # Point d'entrée de l'API, gère le cycle de vie
│   ├── config.py                 # Source de vérité : chemins absolus, clés, modèles
│   ├── graph/
│   │   ├── nodes.py              # Définition des 4 Agents (RAG, Scraper, Narration, Juge)
│   │   ├── router.py             # Logique décisionnelle et aiguillage des agents
│   │   └── pipeline.py           # Assemblage et compilation du graphe LangGraph
│   └── tools/
│       ├── rag_tool.py           # Outils métier : résolution film (_resolve_media),
│       │                         # recherche SQL/PGVector/FAISS, champs honnêtes
│       └── scraper_tool.py       # Fallback web : API REST Wikipédia directe
│                                 # (sans lib wikipedia, retry backoff, User-Agent explicite)
│
└── frontend/                     # 🖥️ INTERFACE UTILISATEUR (Streamlit)
    ├── app.py                    # Application web avec barre de progression et chat
    └── assets/
        ├── fonts/
        │    └── Ghost_Shadow.ttf # Typographie personnalisée pour l'immersion
        └── img/
             └── damonvampface.png # Avatar du bot
```

---

## 🤖 Le Moteur Multi-Agent

Le système décisionnel est orchestré par LangGraph selon une logique **peer-to-peer** (pas de manager central). Le flux suit une chaîne stricte de vérification et de validation :

1. **Agent RAG (Le Chercheur Local)** — Interroge Supabase via `_resolve_media` (résolution déterministe : match exact du titre, puis plus court titre contenant la référence). Évalue si le contexte local est suffisant via un raisonnement Chain-of-Thought. La base locale ne contient **aucune** donnée de réalisateur ni de casting — toute demande sur ces sujets est automatiquement redirigée vers le Scraper. La vérité-terrain SQL brute est transmise directement à la Narration et au Juge (pas de ré-extraction LLM intermédiaire).

2. **Agent Scraper (L'Enquêteur Web)** — Déclenché si le savoir local est insuffisant. Appelle l'API REST Wikipédia directement (sans la lib `wikipedia`, trop fragile) avec retry backoff et User-Agent explicite. Sélection déterministe du bon article (`_pick_best_result` : exact > `(film` > fallback). L'intro de la page est toujours incluse en tête du butin (réalisateur présent dès la première phrase). Dispose d'un fallback déterministe : si le LLM 8B n'émet pas le `tool_call`, le scraper est forcé avec le titre résolu depuis le SQL.

3. **Agent Narration (L'Écrivain Gothique)** — Reçoit uniquement les données brutes (SQL + web), jamais les logs techniques. Règle de fidélité absolue : aucun fait inventé ou altéré, les champs absents sont déclarés avec mépris (« les archives sont muettes »). Réalisateur et casting ne sont cités que s'ils figurent explicitement dans les données web.

4. **Agent Juge (L'Auditeur Suprême)** — Évalue la production sur deux plans : **fact-check** (les faits doivent être sourcés dans les données SQL ou web) et **ton** (cynique, sombre, hautain). Dispose d'un **garde-fou déterministe** : toute année citée absente des sources déclenche un rejet forcé, indépendamment du verdict LLM. En cas de refus, le motif précis est injecté dans le prompt de réécriture. Coupe-circuit à 2 refus → END.

---

## ⚙️ Modèles et Stack Technique

| Composant | Technologie |
|---|---|
| Gestionnaire de paquets | `uv` (ultra-rapide, remplace pip/poetry) |
| LLM Local (Raisonnement & Narration) | `llama3.1` (8B) via Ollama |
| LLM Local (Embeddings) | `nomic-embed-text` via Ollama |
| Base de données | Supabase (PostgreSQL + extension `pgvector`) |
| Mémoire éphémère & Routeur | FAISS (Facebook AI Similarity Search) |
| Orchestration | LangGraph, LangChain |
| Observabilité | Langfuse |
| Enrichissement données | API TMDB (réalisateur, casting, genres, budget) |
| Backend / Frontend | FastAPI, Uvicorn, Streamlit |

---

## 🚀 Installation et Prérequis

### 1. Prérequis Système

* **Python 3.10+**
* L'outil **`uv`**
* **Docker** & Docker Compose (pour Langfuse)
* **Ollama** installé sur le système cible

### 2. Téléchargement des Modèles d'Intelligence Artificielle

L'architecture nécessite Llama 3.1 pour le raisonnement et Nomic pour la vectorisation :

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

### 3. Préparation de l'environnement Python

**Sous Linux / macOS :**

```bash
uv venv
source .venv/bin/activate
uv sync
```

**Sous Windows (PowerShell) :**

```powershell
uv venv
.\.venv\Scripts\activate
uv sync
```

### 4. Observabilité (Langfuse)

Le système utilise Langfuse pour monitorer les appels LLM, les boucles de recadrage du Juge, et le comportement des agents :

```bash
cd path/to/your/langfuse-folder
docker compose up -d
# Puis ouvre http://localhost:3000 pour créer ton projet et récupérer les clés
```

### 5. Configuration de l'environnement (`.env`)

Copie le template documenté et remplis tes clés :

```bash
cp example.env .env
```

```env
# Base de données (Settings → Database → Connection string → Transaction mode port 6543)
SUPABASE_URL="postgresql://postgres.[id]:[mot de passe]@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"

# Observabilité Langfuse (généré via http://localhost:3000)
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="http://localhost:3000"
```

> ⚠️ Ne commite **jamais** le fichier `.env`. Vérifie que `.gitignore` le contient.

---

## 🏁 Démarrage du Système

### Étape 1 : Ingestion des données

Lance le pipeline ETL pour construire les tables et calculer les vecteurs sémantiques. Patientez jusqu'à la fin de la génération des embeddings.

```bash
uv run python supabase_db.py
```

### Étape 2 : Lancement du Moteur (Backend FastAPI)

Démarre le serveur hébergeant les agents LangGraph. Le serveur validera la connexion Supabase, compilera le graphe en mode autonome, et chargera l'index FAISS en RAM.

```bash
uv run uvicorn src.main:app --reload
```

### Étape 3 : Lancement de l'Interface (Frontend Streamlit)

```bash
uv run streamlit run frontend/app.py
```

---

## 🗂️ Gestion du Parquet

| Fichier | Rôle | Colonnes clés |
|---|---|---|
| `horragor_enriched.parquet` | Source de vérité unique (25 colonnes) | title, release_date, vote_average, overview, director, cast_top5, genres, runtime, tagline, budget_tmdb |

`config.py` pointe directement vers ce fichier. À conserver précieusement — il est la source de toute reconstruction de la base.

---

## 🤝 Contribuer

Ouvre une **Issue** pour discuter des changements ou des idées de nouvelles fonctionnalités avant de soumettre une **Pull Request**.

**Règles de contribution :**

* Respecter la séparation des responsabilités : routage (`router.py`) vs logique métier (`nodes.py`).
* Maintenir le *Context Trimming* : ne passer à la Narration que les données brutes, jamais les logs techniques.
* **Le système ne doit jamais halluciner** : toute nouvelle donnée exposée à la Narration doit avoir une source vérifiable (SQL brut ou données web). Les champs absents se déclarent, ne s'inventent pas.
* Les fonctions de routage et les gardes-fous déterministes (résolution de film, vérification d'années) doivent rester **testables unitairement** sans lancer le pipeline complet.