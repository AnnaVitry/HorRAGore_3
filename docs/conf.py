# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# -- Configuration des chemins ------------------------------------------------
# CORRECTION CRITIQUE : on remonte de 2 dossiers (depuis docs/source/) pour atteindre la racine
sys.path.insert(0, os.path.abspath("../.."))

# Variables d'environnement minimales pour éviter que config.py plante pendant l'inspection
os.environ.setdefault("SUPABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")

# -- Informations sur le projet -----------------------------------------------
project = "HorRAGore"
copyright = "2026, Anna Vitry"
author = "Anna Vitry"
release = "3.0"
language = "fr"

# -- Configuration générale ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options pour la sortie HTML ----------------------------------------------
html_theme = "sphinx_rtd_theme"

# Commenté pour éviter une erreur si le dossier n'existe pas encore.
# Décommente-le si tu crées un dossier docs/source/_static/ pour des logos ou du CSS.
# html_static_path = ["_static"]

# -- Configuration de Autodoc -------------------------------------------------
# Permet de forcer l'affichage du code, même pour les fonctions privées
autodoc_default_options = {
    "members": True,
    "private-members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
