Architecture Multi-Agent
========================

HorRAGore utilise LangGraph en mode **peer-to-peer** — pas de manager central.
Le flux est déterministe et testable unitairement.

Graphe d'exécution
-------------------

.. code-block:: text

   START
     │
     ▼
   rag_agent ──(tool_calls)──► tools ──► rag_agent
     │
     ├─(is_sufficient=True)──► narration_agent
     │
     └─(is_sufficient=False)─► scraper_agent ──(tool_calls)──► tools
                                    │
                                    └──────────────────────────► narration_agent
                                                                      │
                                                                      ▼
                                                               quality_control
                                                                      │
                                                          ┌───────────┴──────────┐
                                                      (OUI)                   (NON)
                                                          │                      │
                                                         END            narration_agent
                                                                     (max 2 refus → END)

Agents (nodes.py)
-----------------

.. automodule:: src.graph.nodes
   :members:
   :private-members:
   :undoc-members:

Routeur (router.py)
-------------------

Logique décisionnelle pure — 100% testée unitairement.

.. automodule:: src.graph.router
   :members:
   :undoc-members:

Pipeline (pipeline.py)
-----------------------

Câblage et compilation du graphe LangGraph.

.. automodule:: src.graph.pipeline
   :members:
   :undoc-members:

State partagé (state.py)
-------------------------

.. automodule:: src.models.state
   :members:
   :undoc-members:
