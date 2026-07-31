Backend FastAPI
===============

Point d'entrée de l'API HorRAGore. Expose les routes HTTP,
le middleware Prometheus et le cycle de vie de l'application.

API FastAPI (main.py)
---------------------

.. automodule:: src.main
   :members:
   :private-members:
   :undoc-members:

Configuration (config.py)
--------------------------

.. automodule:: src.config
   :members:
   :undoc-members:

Outils RAG (rag_tool.py)
-------------------------

Résolution de films, recherche SQL et vectorielle PGVector.
Inclut ``_resolve_media`` — le cœur déterministe du pipeline.

.. automodule:: src.tools.rag_tool
   :members:
   :private-members:
   :undoc-members:

Scraper Wikipédia (scraper_tool.py)
-------------------------------------

Fallback web via API REST Wikipédia directe (sans lib wikipedia).

.. automodule:: src.tools.scraper_tool
   :members:
   :private-members:
   :undoc-members:
