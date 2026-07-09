# Frontend

Ce dossier contient l'interface utilisateur minimaliste pour le projet RAGattac.

Fichiers clés
- `app.py` — application frontend (serveur/GUI selon implémentation).
- `pyproject.toml` — métadonnées du projet et dépendances (si Poetry est utilisé).

Exécution
1. Créez et activez un environnement virtuel :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

2. Installer les dépendances (si `requirements.txt` présent) :

```powershell
pip install -r requirements.txt
```

3. Lancer le frontend :

```powershell
python app.py
```

Si vous utilisez Poetry :

```powershell
poetry install
poetry run python app.py
```

Notes
- Ajustez les commandes en fonction de votre environnement (Windows / Unix).
