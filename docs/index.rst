🩸 HorRAGore v3 — Documentation
=================================

.. image:: https://github.com/AnnaVitry/HorRAGore_3/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/AnnaVitry/HorRAGore_3/actions/workflows/ci.yml

.. image:: https://github.com/AnnaVitry/HorRAGore_3/actions/workflows/cd.yml/badge.svg
   :target: https://github.com/AnnaVitry/HorRAGore_3/actions/workflows/cd.yml

.. image:: https://img.shields.io/badge/python-3.12-blue.svg

.. image:: https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white

.. image:: https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi

.. image:: https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white

.. image:: https://img.shields.io/badge/LangGraph-black?style=flat&logo=langchain

----

Bot conversationnel **Multi-Agent** spécialisé en cinéma d'horreur.
Architecture **peer-to-peer** sous LangGraph, RAG local + scraper Wikipédia,
**zéro hallucination** garantie par des garde-fous déterministes.

.. toctree::
   :maxdepth: 2
   :caption: 📚 Documentation

   multiagent
   backend
   database
   frontend

----

🏗️ Architecture du Graphe
--------------------------

.. code-block:: text

   START
     │
     ▼
   rag_agent ──(tool_calls)──► tools ──► rag_agent
     │
     ├─(is_sufficient=True)──────────► narration_agent
     │                                       │
     └─(is_sufficient=False)─► scraper_agent │
                                    │        │
                                    └──────► narration_agent
                                                   │
                                            quality_control
                                                   │
                                       ┌───────────┴──────────┐
                                   (OUI)                   (NON, max 2)
                                       │                      │
                                      END            narration_agent

⚙️ Stack Technique
------------------

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Composant
     - Technologie
   * - LLM Raisonnement
     - ``llama3.1`` (8B) via Ollama
   * - LLM Embeddings
     - ``nomic-embed-text`` via Ollama
   * - Base de données
     - Supabase (PostgreSQL + pgvector)
     - FAISS (cache vectoriel local)
   * - Orchestration
     - LangGraph + LangChain
   * - Observabilité
     - Langfuse + Prometheus + Grafana + Uptime Kuma
   * - Infrastructure
     - Docker Compose (7 services)
   * - Backend / Frontend
     - FastAPI + Streamlit

🚀 Démarrage rapide
--------------------

.. code-block:: bash

   # Lance les 7 services en une commande
   docker compose up -d

.. list-table::
   :widths: 25 25 50
   :header-rows: 1

   * - Service
     - URL
     - Credentials
   * - Frontend
     - http://localhost:8501
     - —
   * - API FastAPI
     - http://localhost:8000
     - —
   * - Langfuse
     - http://localhost:3000
     - Créer un compte au 1er accès
   * - Grafana
     - http://localhost:3001
     - admin / horragor
   * - Prometheus
     - http://localhost:9091
     - —
   * - Uptime Kuma
     - http://localhost:3002
     - Créer un compte au 1er accès

Indices et tables
=================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`