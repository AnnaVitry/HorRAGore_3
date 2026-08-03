import os
import sys

sys.path.insert(0, os.path.abspath(".."))

os.environ.setdefault("SUPABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")

project = "HorRAGore"
copyright = "2026, Anna Vitry"
author = "Anna Vitry"
release = "3.0"
language = "fr"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Thème Furo — moderne, menu latéral, mode sombre/clair
html_theme = "furo"
html_static_path = ["_static"]

html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "top_of_page_button": "edit",
}

html_title = "🩸 HorRAGore v3"

autodoc_default_options = {
    "members": True,
    "private-members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
