"""Configuration pytest globale.

Mocke les variables d'environnement critiques AVANT tout import des modules
du projet, pour éviter que config.py plante (SUPABASE_URL manquante).
Les tests unitaires ne nécessitent aucune connexion DB, Ollama ou réseau.
"""

import os

import pytest


def pytest_configure(config):
    """Injecte les variables d'environnement de test avant la collecte des modules."""
    os.environ.setdefault("SUPABASE_URL", "postgresql://test:test@localhost:5432/test")
    os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-test")
    os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-test")
    os.environ.setdefault("LANGFUSE_HOST", "http://localhost:3000")
