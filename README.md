# 🩸 HorRAGore (Projet de Anna)

## Résumé
HorRAGore est un moteur **RAG (Retrieval-Augmented Generation)** unifié et un pipeline ETL, spécialisé dans l'univers de l'horreur (cinéma, littérature, sci-fi). 

Il repose sur une architecture **Multi-Agent (LangGraph)** tolérante aux pannes. Le système interroge une base de données relationnelle et vectorielle, bascule sur une recherche web (Wikipédia) si le savoir local est insuffisant, et soumet la rédaction finale à un Juge IA. L'objectif : générer des récits horrifiques, cyniques et garantis sans hallucinations.

---

## 🏗️ Architecture du Projet

Le projet est divisé en micro-services (Backend / Frontend / Ingestion / Outils).

```text
HorRAGore_3/
│
├── .env                        # Variables d'environnement (Supabase, Langfuse)
├── pyproject.toml / uv.lock    # Fichiers de gestion des dépendances via 'uv'
├── supabase_db.py              # Script d'ingestion ETL (nettoyage et insertion en base)
│
├── data/                       # Stockage des données locales
│   ├── horragor_final_data.parquet # Le dataset source brut
│   └── faiss_index.bin         # Le cache vectoriel local (généré automatiquement)
│
├── src/                        # 🧠 CŒUR DU BACKEND (FastAPI & LangGraph)
│   ├── main.py                 # Point d'entrée de l'API, gère le cycle de vie
│   ├── config.py               # Source de vérité (Chemins absolus, variables globales)
│   ├── graph/                  
│   │   ├── nodes.py            # Définition des Agents (RAG, Scraper, Narration, Juge)
│   │   ├── router.py           # Logique décisionnelle et aiguillage des agents
│   │   └── pipeline.py         # Assemblage du graphe d'exécution
│   └── tools/                  
│       ├── rag_tool.py         # Outils métier (Recherche SQL, PGVector, Index FAISS)
│       └── scrapper_tool.py    # Outil de secours web (Extraction Wikipédia)
│
└── frontend/                   # 🖥️ INTERFACE UTILISATEUR (Streamlit)
    ├── app.py                  # L'application web avec barre de progression et chat
    └── assets/
        ├── fonts/
        │    └── Ghost_Shadow.ttf # Typographie personnalisée pour l'immersion
        └── img/
             └── damonvampface.png # Avatar du bot

```

---

## 🤖 Le Moteur Multi-Agent

Le système décisionnel est orchestré par LangGraph. Le flux de travail suit une logique stricte de vérification et de validation :

1. **Agent RAG :** Interroge la base locale (Supabase/FAISS) pour extraire les métadonnées. Il évalue si le contexte est suffisant.
2. **Agent Scraper (Fallback) :** Si les données locales sont insuffisantes (ex: demande d'anecdote de tournage), il isole le titre du film et va gratter Wikipédia. Il intègre une sécurité anti-crash si l'API externe ne répond pas.
3. **Agent Narration (HorRAGor) :** L'écrivain cynique. Il condense les informations (locales et web) en un ou deux paragraphes percutants.
4. **Agent Juge (Contrôle Qualité) :** Évalue la production de l'écrivain. Si le texte manque de cynisme ou hallucine des faits, il le rejette et force une réécriture (boucle de recadrage). Les données d'état sont sérialisées au format standard (dictionnaire) pour une stabilité absolue en mémoire.

---

## ⚙️ Modèles et Stack Technique

* **Gestionnaire de paquets :** `uv` (Ultra-rapide, remplace pip/poetry)
* **LLM Local (Raisonnement & Narration) :** `llama3.1` (8B) via Ollama. Garantit l'extraction stricte (Structured Outputs via Pydantic) et un routage précis.
* **LLM Local (Embeddings) :** `nomic-embed-text` via Ollama (Vectorisation sémantique)
* **Base de données (Hybride) :** Supabase (PostgreSQL) avec l'extension `pgvector`
* **Mémoire éphémère & Routeur :** FAISS (Facebook AI Similarity Search)
* **Orchestration & Tracing :** LangGraph, LangChain, Langfuse
* **Backend / Frontend :** FastAPI, Uvicorn, Streamlit

---

## 🚀 Installation et Prérequis

### 1. Prérequis Système

* **Python 3.10+**
* L'outil **`uv`**
* **Docker** & Docker Compose (pour Langfuse)
* **Ollama** installé sur le système cible

### 2. Téléchargement des Modèles d'Intelligence Artificielle

L'architecture nécessite Llama 3.1 pour le raisonnement et Nomic pour la vectorisation. Exécutez :

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

Le système utilise Langfuse pour monitorer les appels LLM, les boucles de recadrage du Juge, et le comportement des agents.

```bash
cd path/to/your/langfuse-folder
docker compose up -d

```

### 5. Configuration de l'environnement (`.env`)

Créez un fichier `.env` à la racine du projet contenant vos clés d'accès.

```env
# Base de données
SUPABASE_URL="postgresql://utilisateur:motdepasse@hote:5432/postgres"

# Observabilité (généré via http://localhost:3000)
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="http://localhost:3000"

```

---

## 🏁 Démarrage du Système

Le lancement s'effectue en 3 étapes distinctes (chaque étape nécessite un terminal séparé).

### Étape 1 : Ingestion des données (Initialisation)

Si votre base de données Supabase est vide, lancez le pipeline ETL pour construire les tables et calculer les vecteurs spatiaux. Patientez jusqu'à la fin de la génération des embeddings.

```bash
uv run python supabase_db.py

```

### Étape 2 : Lancement du Moteur (Backend FastAPI)

Démarrez le serveur hébergeant les agents LangGraph. Le serveur validera la connexion Supabase, compilera le graphe sans interruption humaine (mode autonome), et chargera l'index FAISS en RAM.

```bash
uv run uvicorn src.main:app --reload

```

### Étape 3 : Lancement de l'Interface (Frontend Streamlit)

Assurez-vous que l'environnement virtuel est activé, puis lancez l'interface web pour dialoguer avec HorRAGor.

```bash
uv run streamlit run frontend/app.py

```

---

## 🤝 Contribuer

Ouvrez une **Issue** pour discuter des changements ou des idées de nouvelles fonctionnalités avant de soumettre une **Pull Request**.

**Règles de contribution :**

* Respecter la séparation des responsabilités (Routage vs Logique métier).
* Maintenir le *Context Trimming* (Surface de travail réduite) pour éviter la surcharge cognitive des modèles 8B.
* Le système ne doit jamais halluciner de données techniques externes.
