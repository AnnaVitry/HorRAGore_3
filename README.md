# 🩸 HorRAGore (Projet Lestat)

## Résumé
HorRAGore est un moteur **RAG (Retrieval-Augmented Generation)** unifié et un pipeline ETL, spécialisé dans l'univers de l'horreur (cinéma, littérature sci-fi). Il repose sur une architecture **Multi-Agent (LangGraph)**, interrogeant à la fois une base de données relationnelle et vectorielle pour générer des récits horrifiques précis et garantis sans hallucinations.

---

## 🏗️ Architecture du Projet

Le projet est divisé en micro-services (Backend / Frontend / Ingestion / Outils).

```text
HorRAGore_3/
│
├── .env                        # Variables d'environnement (ex: clés Supabase)
├── pyproject.toml / uv.lock    # Fichiers de gestion des dépendances via 'uv'
├── supabase_db.py              # Script d'ingestion ETL (nettoyage et insertion en base)
│
├── data/                       # Stockage des données locales
│   ├── horragor_final_data.parquet # Le dataset source brut
│   └── faiss_index.bin         # Le cache vectoriel local (généré automatiquement)
│
├── src/                        # 🧠 CŒUR DU BACKEND (FastAPI & LangGraph)
│   ├── main.py                 # Point d'entrée de l'API (FastAPI), gère le cycle de vie
│   ├── config.py               # Source de vérité (Chemins absolus, variables globales)
│   ├── graph/                  # Logique Multi-Agent (LangGraph)
│   │   ├── nodes.py            # Définition des prompts et comportements des Agents (RAG, Narration)
│   │   └── pipeline.py         # Le graphe d'exécution (Aiguillage entre les agents)
│   └── tools/                  
│       └── rag_tool.py         # Outils métier (Recherche SQL, PGVector, Index FAISS)
│
└── frontend/                   # 🖥️ INTERFACE UTILISATEUR (Streamlit)
    ├── app.py                  # L'application web avec barre de progression et chat
    └── assets/
        └── fonts/
            └── police_horragor.ttf # Typographie personnalisée pour l'immersion

```

---

## 🤖 Modèles et Stack Technique

* **Gestionnaire de paquets :** `uv` (Ultra-rapide, remplace pip/poetry)
* **Modèle LLM local :** `llama3.2:3b` via Ollama (Agent narrateur et décisionnel)
* **Modèle d'Embeddings :** `nomic-embed-text` via Ollama (Vectorisation sémantique)
* **Base de données (Hybride) :** Supabase (PostgreSQL) avec l'extension `pgvector`
* **Mémoire éphémère & Routeur :** FAISS (Facebook AI Similarity Search)
* **Orchestration :** LangGraph & LangChain
* **Backend :** FastAPI & Uvicorn
* **Frontend :** Streamlit

---

## 🚀 Installation et Prérequis

### 1. Prérequis système

* **Python 3.10+**
* L'outil **`uv`** installé sur votre machine.
* **Ollama** installé sur votre système (Moteur système indépendant de Python).
* **Installation sous Linux (Ubuntu) :**
```bash
curl -fsSL [https://ollama.com/install.sh](https://ollama.com/install.sh) | sh

```


* *(Pour Windows ou macOS, téléchargez l'installateur officiel sur [ollama.com](https://ollama.com))*



### 2. Téléchargement des Modèles d'Intelligence Artificielle

Une fois Ollama installé, téléchargez les modèles requis en tapant directement dans votre terminal :

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text

```

### 3. Cloner et préparer l'environnement Python

**🐧 Sous Linux / macOS :**

```bash
# 1. Créer l'environnement virtuel avec uv
uv venv

# 2. Activer l'environnement virtuel
source .venv/bin/activate

# 3. Synchroniser et installer toutes les dépendances
uv sync

```

**🪟 Sous Windows (PowerShell) :**

```powershell
# 1. Créer l'environnement virtuel avec uv
uv venv

# 2. Activer l'environnement virtuel
.\.venv\Scripts\activate

# 3. Synchroniser et installer toutes les dépendances
uv sync

```

### 4. Configuration de l'environnement (`.env`)

Créez un fichier `.env` à la racine du projet et ajoutez votre chaîne de connexion Supabase :

```env
SUPABASE_URL="postgresql://utilisateur:motdepasse@hote:5432/postgres"

```

---

## ⚙️ Démarrage du Système

Le lancement se fait en 3 étapes distinctes (chaque étape doit idéalement tourner dans un terminal séparé).

### Étape 1 : Ingestion des données (À ne faire qu'une seule fois)

Si votre base de données Supabase est vide, lancez le pipeline ETL pour construire les tables et calculer les vecteurs spatiaux :

```bash
uv run python supabase_db.py

```

*(Patientez jusqu'à la fin de la génération des embeddings).*

### Étape 2 : Lancement du "Cerveau" (Backend FastAPI)

Démarrez le serveur qui héberge les agents LangGraph et les outils RAG :

```bash
uv run uvicorn src.main:app --reload

```

*(Le serveur vérifiera la connexion Supabase et chargera l'index FAISS en RAM).*

### Étape 3 : Lancement de l'Interface (Frontend Streamlit)

Ouvrez un nouveau terminal, assurez-vous que l'environnement virtuel est activé, puis lancez :

```bash
uv run streamlit run frontend/app.py

```

L'interface web s'ouvrira dans votre navigateur. Vous pouvez maintenant dialoguer avec l'entité HorRAGor.

---

## 🤝 Contribuer

Ouvrez une **Issue** pour discuter des changements ou des idées de nouvelles fonctionnalités avant de soumettre une **Pull Request**. Gardez à l'esprit la règle absolue du *Context Trimming* : le bot ne doit jamais halluciner !

```