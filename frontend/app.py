import base64
import os
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


# --- INJECTION DES POLICES TYPOGRAPHIQUES PERSONNALISÉES ---
def inject_custom_fonts():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # LIGNE À MODIFIER SI LE NOM DE TON FICHIER TTF CHANGE :
    font_path = os.path.join(current_dir, "assets", "fonts", "Ghost Shadow.ttf")

    if not os.path.exists(font_path):
        st.error(f"⚠️ Fichier de police introuvable : {font_path}")
        return

    with open(font_path, "rb") as font_file:
        font_data = font_file.read()
        font_base64 = base64.b64encode(font_data).decode("utf-8")

    st.markdown(
        f"""
        <style>
        @font-face {{
            font-family: 'HorragorTheme';
            src: url(data:font/ttf;charset=utf-8;base64,{font_base64}) format('truetype');
        }}
        
        .titre-horragor {{
            font-family: 'HorragorTheme', sans-serif !important;
            font-size: 5rem;
            color: #ff0000;
            text-align: center;
            text-shadow: 0 0 10px #8b0000, 0 0 20px #8b0000;
            margin-bottom: 5px;
            margin-top: -20px;
        }}

        .projet-lestat {{
            font-family: 'HorragorTheme', sans-serif !important;
            font-size: 3.5rem;
            color: #bf0429;
            text-align: center;
            margin-top: 0px;
        }}
        
        .horror-subtitle {{
            text-align: center;
            color: #8a8a8a;
            font-style: italic;
            margin-bottom: 30px;
        }}
        
        .stSpinner > div {{
            border-top-color: #8b0000 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --- INJECTION DE L'IMAGE DE FOND VAMPIRE ---
def set_background_image(image_filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # On pointe précisément vers le sous-dossier assets/img/
    image_path = os.path.join(current_dir, "assets", "img", image_filename)

    if not os.path.exists(image_path):
        st.warning(f"⚠️ Image de fond introuvable : {image_path}")
        return

    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()

    st.markdown(
        f"""
        <style>
        /* 1. Image de fond sur toute l'application */
        .stApp {{
            background-color: #050505 !important;
            background-image: 
                linear-gradient(to bottom, rgba(5,5,5,0.9) 0%, rgba(5,5,5,0.15) 35%, rgba(5,5,5,0.95) 100%),
                url("data:image/jpeg;base64,{encoded_string}");
            background-position: bottom center;
            background-repeat: no-repeat;
            background-size: cover;
            background-attachment: fixed;
        }}
        
        /* 2. Contraste pour les bulles de discussion */
        .stChatMessage {{
            background-color: rgba(10, 10, 10, 0.7) !important;
            border-radius: 10px;
            border: 1px solid rgba(139, 0, 0, 0.3);
            padding: 12px;
        }}

        /* 3. SIDEBAR TRANSLUCIDE AVEC FLOU (Glassmorphism) */
        [data-testid="stSidebar"] {{
            background-color: rgba(5, 5, 5, 0.4) !important; /* Fond noir très transparent */
            backdrop-filter: blur(15px) !important; /* Effet de flou diffus */
            -webkit-backdrop-filter: blur(15px) !important; /* Compatibilité Safari */
            border-right: 1px solid rgba(139, 0, 0, 0.2) !important; /* Légère bordure sang pour la délimitation */
        }}

        /* Rend le header de la sidebar transparent pour ne pas casser l'effet */
        [data-testid="stSidebarHeader"] {{
            background-color: transparent !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# Appel immédiat de l'injection CSS et fond d'écran
inject_custom_fonts()
# set_background_image("damonvampface.jpg")
set_background_image("damonvampface.png")

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 class='projet-lestat'>⚜️ MENU ⚜️</h2>", unsafe_allow_html=True)
    st.write("Projet de Anna :)")
    st.markdown("---")
    st.markdown("**Statut du Système :**")

    # Indicateur dynamique visuel dans la sidebar
    try:
        response = requests.get("http://localhost:8000/", timeout=180)
        st.success("💚 API FastAPI En Ligne")
    except requests.exceptions.RequestException:
        st.error("❤️ API FastAPI Hors-ligne")

    st.markdown("---")
    st.markdown(
        "<small>Modèle : Architecture ReAct & Base Hybride Supabase</small>",
        unsafe_allow_html=True,
    )


# --- CORPS PRINCIPAL DE L'INTERFACE ---
st.markdown("<h1 class='titre-horragor'>HORRAGOR</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='horror-subtitle'>L'agent qui sonde les abysses du cinéma d'horreur...</p>",
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
            current_percentage = int((i + 1) * (80 / len(LOADING_STEPS)))
            progress_bar.progress(current_percentage)
            time.sleep(0.5)

        progress_text.markdown(
            "⚡ *Établissement du contact avec le serveur d'outils...*"
        )

        # Étape B : Appel réel vers l'API FastAPI de ton binôme
        try:
            payload = {"user_id": "stream_user_1", "question": last_user_message}
            response = requests.post(BACKEND_URL, json=payload, timeout=180)

            progress_bar.progress(100)
            time.sleep(0.2)

            if response.status_code == 200:
                answer = response.json().get("answer", "L'entité refuse de répondre...")
            else:
                answer = f"⚠️ **Malédiction du Serveur** : Erreur HTTP {response.status_code}. Détail : {response.text}"

        except requests.exceptions.ConnectionError:
            progress_bar.progress(100)
            random_quote = random.choice(FASTAPI_ERROR_QUOTES)
            answer = f"{random_quote}\n\n*Veuillez vérifier que votre binôme a bien réveillé le serveur FastAPI.*"
        except Exception as e:  # noqa: BLE001
            progress_bar.progress(100)
            answer = f"💥 **Distorsion de la réalité** : Une erreur inattendue est survenue : {e!s}"

        # Étape C : Nettoyage des éléments de chargement et affichage de la réponse finale
        progress_text.empty()
        progress_bar.empty()
        st.markdown(answer)

    # Enregistrement final et réinitialisation de l'état pour débloquer l'input
    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.processing = False
    st.rerun()
