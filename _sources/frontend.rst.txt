Frontend Streamlit
==================

Interface utilisateur de HorRAGore. Communique avec le backend
FastAPI via l'URL configurable ``API_URL`` (dynamique en Docker).

Fonctionnalités
---------------

* Chat en temps réel avec barre de progression
* Indicateur de statut API (💚 En ligne / ❤️ Hors-ligne)
* Typographie personnalisée Ghost Shadow
* Avatar du bot (Damon Vampire)

Configuration Docker
--------------------

En mode Docker, la variable ``API_URL`` est injectée par ``docker-compose.yml`` :

.. code-block:: yaml

   environment:
     API_URL: http://api:8000

En développement local, l'URL par défaut est ``http://localhost:8000``.

Application (frontend/app.py)
------------------------------

.. automodule:: frontend.app
   :members:
   :undoc-members:
