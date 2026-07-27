LangGraph HorRAGor_ Graphe et Boucles.pdf
pdf


router.py
79 lignes

py


pipeline.py
106 lignes

py


nodes.py
208 lignes

py


state.py
39 lignes

py


chat_models.py
25 lignes

py


scrapper_tool.py
66 lignes

py


rag_tool.py
197 lignes

py


misc_tools.py
28 lignes

py


README.md
179 lignes

md

lit le chat langraph boucle et les autres fichier de mon projet Horragore. Est ce une bonne approche?


Scrutinized architecture, unearthed dead code and correction loop flaws
Scrutinized architecture, unearthed dead code and correction loop flaws
J'ai lu le chat Gemini (« Graphe et Boucles ») et les fichiers du projet. Un point important d'abord : le PDF que j'ai reçu (LangGraph_HorRAGor__Graphe_et_Boucles.pdf) est en réalité la retranscription de ta conversation Gemini, pas le cahier des charges « HorRAGore 3 ». Je n'ai donc pas les directives officielles de l'exercice sous les yeux — je juge donc l'architecture sur ses mérites propres, et je te dirai où mon verdict dépendrait du spec que je ne vois pas.

Sur le fond : l'approche globale est saine. Le multi-agent en relais (sans superviseur central), l'isolation du contexte pour l'écrivain, et la boucle Juge avec coupe-circuit sont de bonnes décisions. Les compliments de Gemini là-dessus sont mérités. Mais il y a des failles réelles, dont une que Gemini a complètement ratée.

1. Le faux Scraper (Gemini a raison, et c'est même pire). Ton scraper_node n'émet jamais de tool_calls : il appelle scrape_detailed_synopsis.invoke(...) en dur et retourne {"web_anecdotes": [...]}. Donc la branche scraper_agent → tools est du code mort. Deux aggravations que Gemini n'a pas relevées : (a) ton tools_node = ToolNode(rag_tools) ne connaît que les outils RAG — scrape_detailed_synopsis n'y est même pas enregistré, donc la branche scraper_agent de route_after_tools est morte elle aussi ; (b) comme le scraper écrit dans web_anecdotes et pas dans messages, ton route_after_scraper lit un messages[-1] périmé (la réponse du RAG). Ça marche par accident, pas par design.

2. La « boucle de correction » n'en est pas une (Gemini a raté ça — c'est le point le plus grave). Quand le Juge refuse, il empile un HumanMessage « REFUSÉ » avec le motif. Mais regarde narration_node : il invoque le LLM avec [system_prompt, sterile_command] uniquement. Il ne passe jamais l'historique messages au modèle. Autrement dit, l'écrivain ne voit jamais la critique du Juge : il régénère à l'aveugle, avec exactement le même prompt, et compte sur le hasard de temperature=0.3 pour tomber mieux. Le « REFUSÉ » ne sert qu'à incrémenter ton compteur de sortie. Ce n'est pas une boucle de recadrage, c'est un retry aléatoire déguisé. Si tu veux une vraie correction, il faut réinjecter verdict["critique"] (ou le dernier message « REFUSÉ ») dans le prompt de narration_node.

3. Robustesse asymétrique. Ta boucle Juge a un coupe-circuit (2 refus → END, propre). Mais la boucle rag_agent ↔ tools n'en a aucune : si le LLM 8B re-demande des outils à chaque passage, tu tournes jusqu'au recursion_limit de LangGraph (25 par défaut) puis ça crashe au lieu de dégrader gracieusement. À surveiller.

4. Le drapeau is_database_sufficient. La critique finale de Gemini est juste : ta liste de mots-clés en dur (tournage/anecdote/secret) est aveugle à « coulisses », « making of », « fun fact »… Et le double appel LLM dans rag_node (le tool-bound puis l'extracteur structuré) coûte de la latence sur un 8B.

Sur la solution que Gemini te propose (ajouter un champ de raisonnement Chain-of-Thought dans RagHarvest avant le booléen) : c'est une amélioration correcte, mais elle soigne le symptôme. Le vrai problème est ailleurs — ton harvest_prompt établit que la base ne contient par conception aucune info de tournage/production. Donc la décision ne devrait pas être « le LLM juge-t-il ses données suffisantes ? » (tu demandes à un 8B d'être honnête sur ses propres limites, ce qu'il déteste faire), mais plutôt une classification d'intention de la question en amont : « cette question porte-t-elle sur la production/les coulisses ? → scraper, sinon → local ». Déterministe là où c'est possible, ça bat le self-grading. Le CoT peut compléter, pas remplacer.

Un dernier détail : le tout premier message de Gemini proposait un guardrail_node (rejet des requêtes hors-sujet type « météo »). Il n'a jamais été intégré — ton graphe démarre direct sur rag_agent. Selon ce que demande le cahier des charges HorRAGore 3, ça peut être une lacune ou non.

Si tu m'envoies le vrai PDF des directives HorRAGore 3, je peux vérifier la conformité point par point plutôt que de deviner. Et si tu veux, je te réécris concrètement le narration_node pour que la boucle Juge corrige vraiment — c'est le correctif à plus fort impact.

HorRAGor BOT Partie 3.pdf
pdf

ok et voici le lien github vers mon projet en etat https://github.com/AnnaVitry/HorRAGore_3.git


Inventoried code against spec, identified discrepancies, resolved to verify GitHub implementation
Inventoried code against spec, identified discrepancies, resolved to verify GitHub implementation
Maintenant j'ai le vrai cahier des charges. Laisse-moi vérifier l'état actuel du repo pour combler les fichiers que je n'avais pas (main.py, config.py, le frontend) — ce sont justement ceux dont dépend une partie du verdict.


Orchestrated API access pour contourner les restrictions web
Orchestrated API access pour contourner les restrictions web
web_fetch is blocked on GitHub, but mon environnement a un accès réseau à l'API GitHub. Je récupère l'arborescence et les fichiers manquants directement.


Exécuté 2 commandes
Exécuté 2 commandes
API rate-limitée sur l'IP partagée. Je clone le repo directement (github.com est autorisé).


Clone repo and list files
Clone repo and list files
Le repo est cloné. Je lis les fichiers clés que je n'avais pas — surtout main.py (pour vérifier Langfuse) et config.py.


Scrutant la configuration du pipeline en mode autonome
Scrutant la configuration du pipeline en mode autonome
main.py récupéré. Un dernier point à vérifier : le frontend appelle-t-il bien l'API.


Audité l'implémentation contre les spécifications et identifié des fonctionnalités non fonctionnelles
Audité l'implémentation contre les spécifications et identifié des fonctionnalités non fonctionnelles
J'ai maintenant le vrai cahier des charges et l'état actuel du repo (y compris main.py, config.py et le frontend que je n'avais pas). Verdict global d'abord : oui, c'est une bonne approche, et elle est même conforme au spec sur l'essentiel. Le problème n'est pas l'architecture — c'est que plusieurs fonctionnalités que tu as ajoutées au-delà du spec sont câblées mais mortes à l'exécution.

Ce que le spec HorRAGore 3 demande, et que tu as bien. Le cahier des charges d'Antony ne réclame que trois choses structurantes : une architecture peer-to-peer sans manager central, trois agents (RAG → Scraper conditionnel → Narration) partageant un State, et l'isolation de la Narration. Les trois sont là. Ton narration_node est même exemplaire sur le point le plus subtil du spec (« isolé de toute la plomberie technique pour éviter la collision de tokens ») : tu n'injectes que local_lore et web_data, jamais les logs SQL ni les dumps Wikipédia. La séparation nodes / router (fonctions qui renvoient un str, testables unitairement) / pipeline respecte à la lettre les « règles d'or LangGraph » du PDF. Et Langfuse est bien intégré via CallbackHandler avec config={"callbacks":[...]} passé à l'invoke, comme demandé au chapitre Monitoring. Sur le contrat, tu es en règle.

Petits écarts de nommage par rapport à l'arborescence du PDF, cosmétiques mais faciles à corriger si on te note dessus : le spec dit scraper_tool.py (tu as scrapper_tool.py, double p), app_frontend.py à la racine (tu as frontend/app.py), et « le fichier se termine par app = workflow.compile() » (tu nommes l'objet app_graph). Rien de grave.

Maintenant les vrais problèmes, du plus grave au moins grave. Tous concernent des ajouts hors-spec (Juge, HITL, nœud tools), donc pas des manquements au cahier des charges — mais du code qui ne fait pas ce qu'il prétend faire, ce qui est exactement le genre de chose qu'un correcteur relève.

1. Le Human-in-the-Loop est du code mort (nouveau, vu dans main.py). Ton main.py contient ~40 lignes de validation humaine : if state_info.next: → input("VALIDATION : Autoriser l'action ? (oui/non)") → reprise ou injection d'un ToolMessage de refus. Ce bloc suppose que le graphe se suspende avant tools. Or dans pipeline.py, la ligne interrupt_before=["tools"] est commentée et tu compiles en mode autonome (workflow.compile(checkpointer=memory)). Sans interruption, invoke va jusqu'à END, donc state_info.next est toujours vide → le bloc HITL ne s'exécute jamais. Soit tu réactives interrupt_before=["tools"] pour que la validation fonctionne, soit tu supprimes ce bloc de main.py. En l'état il donne l'illusion d'une feature qui n'existe pas au runtime.

2. La « boucle de correction » du Juge ne corrige rien (confirmé dans nodes.py). C'est le point que Gemini a raté et que je maintiens. Le Juge empile un HumanMessage « REFUSÉ. Motif : … », mais narration_node invoque le LLM avec [system_prompt, sterile_command] uniquement — il ne passe jamais messages. L'écrivain ne voit donc jamais la critique : il régénère à l'identique en pariant sur le hasard de temperature=0.3. Ton compteur de « REFUSÉ » ne sert qu'à sortir de la boucle, pas à améliorer le texte. C'est un retry aléatoire déguisé en recadrage.

3. Le faux Scraper et les branches tools mortes (confirmé). scraper_node appelle scrape_detailed_synopsis.invoke(...) en dur et retourne web_anecdotes — il n'émet jamais de tool_calls. Donc la branche scraper_agent → tools du pipeline ne se déclenche jamais. Pire : ton tools_node = ToolNode(rag_tools) ne connaît que les outils RAG, scrape_detailed_synopsis n'y est pas enregistré, donc la branche scraper_agent de route_after_tools est morte aussi. Ça « marche » parce que le flux passe toujours directement à la narration. Note : le spec parle d'un scraper_tool.py « natif » sans exiger qu'il soit un tool_call LangGraph — donc l'exécution synchrone est acceptable au regard du cahier des charges. Ce qu'il faut, c'est assumer ce choix et nettoyer les branches conditionnelles fantômes, sinon garder la cohérence est impossible.

4. Aucun coupe-circuit sur la boucle rag_agent ↔ tools. Ta boucle Juge, elle, a son garde-fou (2 refus → END, propre et conforme à l'esprit du spec). Mais si le 8B redemande un outil à chaque passage RAG, tu montes jusqu'au recursion_limit de LangGraph (25 par défaut) et ça crashe au lieu de dégrader. Asymétrie à combler.

5. Le drapeau is_database_sufficient (la critique finale de Gemini, toujours valide). Ta liste de mots-clés en dur (tournage/anecdote/secret) est aveugle à « coulisses », « making of », « fun fact ». Le CoT que Gemini propose aide, mais le fond du problème est que tu demandes à un 8B complaisant d'auto-évaluer ses propres lacunes. Plus robuste : classifier l'intention de la question en amont (« porte sur la production/coulisses ? → scraper ») plutôt que de faire auto-noter le modèle. Déterministe là où c'est possible.

En résumé pour ta soutenance. Le socle demandé par le PDF est bon et conforme. Le risque, c'est que tu as greffé trois features non demandées (HITL, Juge-correcteur, Scraper agentique via tools) qui sont inertes au runtime. Deux stratégies défendables : soit tu les fais vraiment fonctionner, soit — vu que le spec ne demande que 3 agents + Langfuse — tu les retires pour livrer une version minimale mais honnête, où tout ce qui est câblé s'exécute réellement. Un correcteur préfère presque toujours 3 agents qui marchent à 6 dont la moitié sont du décor.

Le correctif à plus fort impact reste le #2 : réinjecter verdict["critique"] dans le prompt de narration_node pour que la boucle corrige pour de vrai. Si tu veux, je te réécris ce nœud proprement, et je peux aussi te donner le patch pour trancher le #1 (HITL) dans un sens ou dans l'autre.


Diagnosed budget data corruption and traced upstream ETL pipeline failure
Diagnosed budget data corruption and traced upstream ETL pipeline failure
« 0 partout » — ça change le diagnostic. Ton budget n'est ni NULL ni correct : il vaut 0. Donc ton outil SQL renvoie honnêtement « Budget: 0$ », le CoT interprète (raisonnablement) 0 comme « pas de vraie donnée » et dévie vers le Scraper, qui fait un no-op, et la narration comble le trou avec « 11 millions » tiré des connaissances de llama. La racine, c'est la donnée.

J'ai justement ton fichier source dans le repo (data/horragor_final_data.parquet). Je peux vérifier tout de suite si le problème vient de l'ingestion (supabase_db.py qui perd le budget) ou de la source (le parquet n'a jamais eu de budgets) :


Investigated données manquantes et interrogé fiabilité requête
Investigated données manquantes et interrogé fiabilité requête
La source elle-même a budget = 0 pour ces lignes — donc ce n'est pas ton ingestion, c'est la donnée d'origine. Mais je remarque un truc plus grave : ces 161 lignes « alien » sont des films obscurs (Alienation, Alien Tornado…), pas le Alien de Ridley Scott (1979). Or ton outil SQL fait ilike('%alien%').first() → il renvoie le premier match, probablement pas le bon film. Je creuse :


Diagnosed budget data corruption and query retrieval misalignment issues
Diagnosed budget data corruption and query retrieval misalignment issues
Voilà le vrai diagnostic, et il est plus profond que « budget manquant ». Trois problèmes de données/récupération se cumulent :

1. Ton outil SQL renvoie le mauvais film. query_movie_metadata fait ilike('%alien%').first() — or %alien% matche 161 films, et .first() (sans ORDER BY) attrape le premier physique, ici « Alienation » (2026), pas le Alien de Ridley Scott. Donc toute la métadonnée « récoltée » concernait probablement le mauvais film. Le vrai Alien (1979) existe bien dans ta base, mais il n'a jamais été ciblé.

2. Le budget est vide sur TOUTE la base. 9978 lignes à 0, 0 ligne avec un budget > 0, le reste à null. Aucun film n'a de budget exploitable. Le Alien de Ridley Scott lui-même est à null. Donc aucune question budget ne peut être répondue depuis tes données — jamais.

3. Il n'existe aucune colonne « réalisateur ». Donc « réalisé par Ridley Scott » est 100 % halluciné par llama. Comme « 1979 » (la ligne réellement lue, Alienation, est datée 2026) et comme « 11 millions ».

Autrement dit : sur ta question, la quasi-totalité de la réponse était inventée, parce que (a) le mauvais film a été récupéré et (b) la narration comble tous les trous avec les connaissances de llama. C'est exactement le contraire de l'objectif « sans hallucination » du README.

Je vérifie un dernier point : tu as une classe FastMovieRouter (FAISS) dans rag_tool.py censée résoudre le bon film — est-elle seulement utilisée ?


Diagnostiqué dysfonctionnement de recherche et hiérarchisé corrections prioritaires
Diagnostiqué dysfonctionnement de recherche et hiérarchisé corrections prioritaires
Dernière pièce du puzzle : FastMovieRouter (ta désambiguïsation FAISS) est défini mais jamais appelé — encore du code mort. Ton outil se contente donc du ilike().first(), d'où le mauvais film. Le diagnostic est complet.

Récapitulatif du bug (une seule cause en cascade)
Ta question « budget d'Alien » a échoué en chaîne : le SQL a récupéré le mauvais film (Alienation 2026 au lieu d'Alien 1979), la base n'a aucun budget (0/null partout) ni aucun réalisateur, et la narration a tout inventé pour combler. Le CoT, lui, a plutôt bien joué son rôle (il a vu que le budget manquait). Le problème n'est pas ton graphe — il est dans la récupération et dans l'honnêteté de l'Écrivain.

Plan de correctifs, par priorité
Fix 1 — Désambiguïser query_movie_metadata (le plus important). Remplacer ilike('%x%').first() par : match exact d'abord (title == référence), puis à défaut le plus court titre contenant la requête (« Alien » gagne contre « Alienation »/« Alien Nation »). Ça garantit qu'on lit le bon film. Plus simple et plus fiable que de réveiller le FastMovieRouter FAISS (dont le seuil 0.5 est lui-même fragile, comme le note ton propre commentaire).

Fix 2 — Anti-hallucination de la narration (critique vu la donnée creuse). Interdire explicitement à l'Écrivain d'utiliser ses connaissances hors des données fournies ; si une info est absente, il doit la déclarer « inconnue » avec cynisme plutôt que l'inventer. C'est ce qui sert directement le « sans hallucination » du README, et sans ça, avec une base à 99,5 % de budgets vides, llama comblera toujours.

Fix 3 — Présenter proprement les champs absents. Dans l'outil SQL, quand budget/revenue/note valent 0 ou null, renvoyer « non renseigné » au lieu de « 0$ ». Ça évite que le CoT prenne un 0 pour une vraie valeur et que le budget vide déclenche le Scraper à tort.

Fix 4 — Fallback du Scraper (secondaire). Forcer le tool_call si llama ne l'émet pas. Utile, mais moins urgent que 1–3.

Un point stratégique honnête : avec ces données (pas de budget, pas de réalisateur), ton bot est fort sur le synopsis, les notes, les recommandations (pgvector), la date, l'univers et les anecdotes scrapées — mais budget et réalisateur ne sont tout simplement pas dans la donnée. Le Fix 2 le fera dire élégamment.

Je propose d'attaquer Fix 1 + 3 + 2 ensemble (c'est le trio qui répare précisément ton test Alien), puis le Fix 4 juste après. Je te les prépare dans cet ordre, ou tu veux commencer par un autre ?

ok allon y


Architected systematic code fixes with helper function extraction and validation
Architected systematic code fixes with helper function extraction and validation
« Allons-y ». Je fais le trio Fix 1 + 3 + 2. Je commence par rag_tool.py. Je regarde le texte exact à modifier :


Reconfigured SQLAlchemy imports strategically
Reconfigured SQLAlchemy imports strategically
Fix 1 (désambiguïsation) + Fix 3 (champs absents honnêtes). D'abord l'import sqlalchemy (or_ n'est plus utile, j'ajoute func) :


Swap or_ for func in sqlalchemy imports
Swap or_ for func in sqlalchemy imports
J'ajoute le helper de résolution _resolve_media juste après la connexion. Je récupère l'ancre exacte :


A exécuté une commande, fichier modifié
A exécuté une commande, fichier modifié
Maintenant query_movie_metadata : résolution correcte + présentation honnête des champs à 0/null :


Use resolver and present missing budget/note/date honestly
Use resolver and present missing budget/note/date honestly
Même correction de résolution dans find_similar_horror_movies (sinon les recommandations partent aussi du mauvais film) :


Examined narration system to eliminate hallucinations
Examined narration system to eliminate hallucinations
rag_tool.py fait. Fix 2 — anti-hallucination de la narration dans nodes.py :


Verified code compilation and tested disambiguation logic
Verified code compilation and tested disambiguation logic
Je compile, je vérifie qu'il ne reste pas de or_ orphelin, et surtout je valide l'heuristique de désambiguïsation sur tes vraies données (le plus court titre contenant « alien » doit bien être « Alien ») :


Compile, check orphan or_, validate disambiguation heuristic on real data
Compile, check orphan or_, validate disambiguation heuristic on real data
