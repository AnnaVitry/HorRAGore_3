import random
import time

import requests
import streamlit as st

# URL de l'API FastAPI de ton binôme
BACKEND_URL = "http://localhost:8000/chat"

# --- BANQUE DE PHRASES D'ERREUR ALÉATOIRES (Horreur & SF) ---
FASTAPI_ERROR_QUOTES = [
    "👹 Le signal radio du Nostromo est coupé... L'entité a sectionné les câbles du serveur.",
    "👹 'I'm sorry Dave, I'm afraid I can't do that.' Le supercalculateur ne répond plus.",
    "👹 Une présence occulte parasite la ligne. Le port 8000 est scellé par le sang.",
    "👹 Les circuits brûlent... Quelque chose s'est échappé du laboratoire de recherche.",
    "👹 'Ils sont icicici...' Les esprits frappeurs saturent les requêtes réseau.",
    "👹 Signal perdu dans la stratosphère. La cabane au fond des bois n'a plus d'électricité.",
    "👹 Échec du saut hyperespace. Le cerveau de HorRAGor dérive dans le vide intersidéral.",
    "👹 Le protocole de confinement a échoué. L'API a été dévorée par un Xénomorphe.",
    "👹 Une distorsion temporelle bloque la connexion. Êtes-vous sûr que le serveur existe dans cette ligne temporelle ?",
]

# --- BANQUE DE PHRASES DE CHARGEMENT DYNAMIQUE ---
LOADING_STEPS = [
    "🩸 Incantation du script d'ingestion...",
    "💀 Réveil des entités de la base Supabase...",
    "👁️ Alignement des vecteurs sémantiques...",
    "🧠 HorRAGor extrait les données du Grimoire...",
    "⚖️ Le Juge examine la réponse pour éviter les hallucinations...",
    "⚰️ Restitution finale imminente...",
]

# Configuration de la page avec un layout adapté
st.set_page_config(page_title="HorRAGor BOT", page_icon="🩸", layout="centered")

# --- STYLE CSS PERSONNALISÉ ---
st.markdown(
    """
    <style>
    .horror-title {
        font-family: 'Courier New', Courier, monospace;
        color: #ff0000;
        text-align: center;
        text-shadow: 0 0 10px #8b0000, 0 0 20px #8b0000;
        font-size: 3rem;
        font-weight: bold;
        margin-bottom: 0px;
    }
    .horror-subtitle {
        text-align: center;
        color: #8a8a8a;
        font-style: italic;
        margin-bottom: 25px;
    }
    .stSpinner > div {
        border-top-color: #8b0000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(
        "<h2 style='color: #8b0000; font-family: monospace;'>🚀 USCSS Prometheus</h2>",
        unsafe_allow_html=True,
    )
    st.write("Projet de Groupe - RAG Horreur et SCI/FI")
    st.markdown("---")
    st.markdown("**Statut du Système :**")

    # Indicateur dynamique visuel dans la sidebar
    try:
        # On tente une requête très rapide juste pour voir si le port écoute
        res = requests.get("http://localhost:8000/", timeout=0.5)
        st.success("🟢 API FastAPI En Ligne")
    except:
        st.error("🔴 API FastAPI Hors-ligne")

    st.markdown("---")
    st.markdown(
        "<small>Modèle : Architecture ReAct & Base Hybride Supabase</small>",
        unsafe_allow_html=True,
    )

# --- CORPS PRINCIPAL DE L'INTERFACE ---
st.markdown("<p class='horror-title'>🩸 HorRAGor 🛸</p>", unsafe_allow_html=True)
st.markdown(
    "<p class='horror-subtitle'>L'agent qui sonde les abysses du cinéma, de la littérature sci/fi et du jeu vidéo d'horreur...</p>",
    unsafe_allow_html=True,
)

# 1. Initialisation des états de session
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processing" not in st.session_state:
    st.session_state.processing = False


# 2. Fonction de callback pour figer l'input dès qu'on valide
def disable_input():
    st.session_state.processing = True


# 3. Zone de saisie thématique (Désactivée si l'assistant réfléchit)
prompt = st.chat_input(
    "Partagez votre phobie (ex: Parle-moi du film Alien)... 🧟",
    disabled=st.session_state.processing,
    on_submit=disable_input,
)

# 4. Affichage de tout l'historique des discussions (Avec avatars thématiques)
for message in st.session_state.messages:
    avatar = "👻" if message["role"] == "user" else "🧛‍♂️"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# 5. Traitement immédiat de la saisie utilisateur
if prompt:
    with st.chat_message("user", avatar="🧟"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# 6. LOGIQUE D'APPEL AVEC BARRE DE CHARGEMENT ANIMÉE ROUGE SANG
if st.session_state.processing and st.session_state.messages:
    last_user_message = st.session_state.messages[-1]["content"]

    with st.chat_message("assistant", avatar="👹"):
        # Conteneurs vides pour modifier dynamiquement les étapes de chargement
        progress_text = st.empty()
        progress_bar = st.progress(0)

        # Étape A : On fait défiler les messages d'ambiance et monter la jauge (0% à 80%)
        for i, quote in enumerate(LOADING_STEPS):
            progress_text.markdown(f"*{quote}*")
            # Calcule un pourcentage progressif basé sur l'étape actuelle
            current_percentage = int((i + 1) * (80 / len(LOADING_STEPS)))
            progress_bar.progress(current_percentage)
            time.sleep(
                0.5
            )  # Petit délai pour laisser le temps de lire le lore d'horreur

        progress_text.markdown(
            "⚡ *Établissement du contact avec le serveur d'outils...*"
        )

        # Étape B : Appel réel vers l'API FastAPI de ton binôme
        try:
            # CORRECTION 1 : On ajoute un "user_id" fixe (ou généré) pour respecter le modèle Pydantic
            payload = {"user_id": "stream_user_1", "question": last_user_message}

            response = requests.post(BACKEND_URL, json=payload, timeout=45)

            # Si le serveur a répondu, on pousse la jauge à 100% juste avant d'afficher
            progress_bar.progress(100)
            time.sleep(0.2)

            if response.status_code == 200:
                # CORRECTION 2 : On cherche la clé "answer" et non "response"
                answer = response.json().get("answer", "L'entité refuse de répondre...")
            else:
                answer = f"⚠️ **Malédiction du Serveur** : Erreur HTTP {response.status_code}. Détail : {response.text}"

        except requests.exceptions.ConnectionError:
            progress_bar.progress(100)
            # Pioche une phrase d'erreur d'horreur au hasard
            random_quote = random.choice(FASTAPI_ERROR_QUOTES)
            answer = f"{random_quote}\n\n*Veuillez vérifier que votre binôme a bien réveillé le serveur FastAPI.*"
        except Exception as e:
            progress_bar.progress(100)
            answer = f"💥 **Distorsion de la réalité** : Une erreur inattendue est survenue : {str(e)}"

        # Étape C : Nettoyage des éléments de chargement et affichage de la réponse finale
        progress_text.empty()
        progress_bar.empty()
        st.markdown(answer)

    # Enregistrement final et réinitialisation de l'état pour débloquer l'input
    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.processing = False
    st.rerun()
