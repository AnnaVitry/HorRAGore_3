# RAGattac

Résumé
-	RAGattac est un petit projet d'exploration RAG (Retrieval-Augmented Generation) contenant un script principal (`main.py`) et une interface frontend légère dans le dossier `frontend/`.

Structure du dépôt
- `main.py` — point d'entrée principal du projet (backend / orchestrateur)
- `frontend/` — application frontend incluant `app.py` et le fichier `pyproject.toml`

Prérequis
- Python 3.10+ installé
- (Optionnel) virtualenv / venv pour isoler les dépendances

Installation et lancement (général)
1. Créer et activer un environnement virtuel:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

2. Installer les dépendances (si un `requirements.txt` existe) :

```powershell
pip install -r requirements.txt
```

3. Lancer le script principal :

```powershell
python main.py
```

Frontend (dossier `frontend/`)
- Le frontend contient `app.py` et un `pyproject.toml`.
- Pour l'exécuter :

```powershell
cd frontend
python app.py
```

Si vous utilisez Poetry :

```powershell
cd frontend
poetry install
poetry run python app.py
```

Contribuer
- Ouvrez une issue pour discuter des changements avant d'envoyer une pull request.

Licence
- Ajoutez ici la licence applicable (ex. MIT) ou supprimez cette section si non pertinente.

Contact
- Questions / retours : créez une issue ou contactez l'auteur du dépôt.
