import base64
import html
import json
import pathlib
import streamlit as st
from PIL import Image
# On importe le moteur pour que l'assistant puisse lire les vraies données
from moteur import charger_fusion, ACTION
import auth
import diffusion
import store

RACINE = pathlib.Path(__file__).resolve().parent
ASSETS = RACINE / "assets"
REGLAGES = RACINE / "data" / "reglages.json"
DEFAUT = {"mode": "nuit", "fond": "", "accueil": "", "voile": 55, "flou": 16}

COULEURS = {
    "Vert": ("#1F8A4C", "#fff"), "Jaune": ("#ECF553", "#010860"),
    "Orange": ("#F59E0B", "#010860"), "Rouge": ("#F80001", "#fff"),
    "Indéterminé": ("#8b93c9", "#010860"),
}

THEMES = {
    "nuit": dict(txt="#FFFFFF", accent="#ECF553", f1="#010860", f2="#2C3C9E",
                 verre="rgba(255,255,255,.10)", bord="rgba(255,255,255,.22)",
                 neo="#1a2a8a", champ="#0a1470", bg_pop="#010860",
                 ombre1="rgba(0,0,20,.5)", ombre2="rgba(80,100,220,.35)", rgb="1,8,96"),
    "jour": dict(txt="#010860", accent="#2C3C9E", f1="#EEF1FF", f2="#C9D1FF",
                 verre="rgba(255,255,255,.60)", bord="rgba(1,8,96,.15)",
                 neo="#E4E8FF", champ="#FFFFFF", bg_pop="#FFFFFF",
                 ombre1="rgba(1,8,96,.22)", ombre2="rgba(255,255,255,.95)", rgb="238,241,255"),
}

def lire():
    r = store.reglages_lire()          # table MySQL `reglages` (None en mode fichiers)
    if r is not None:
        return {**DEFAUT, **r}
    try:
        return {**DEFAUT, **json.loads(REGLAGES.read_text(encoding="utf-8"))}
    except Exception:
        return dict(DEFAUT)

def ecrire(r):
    if store.mysql_actif():
        store.reglages_ecrire(r)
        return
    REGLAGES.parent.mkdir(exist_ok=True)
    REGLAGES.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")

def enregistrer_image(cle, fichier):
    ASSETS.mkdir(exist_ok=True)
    img = Image.open(fichier).convert("RGB")
    img.thumbnail((1920, 1920))
    img.save(ASSETS / f"{cle}.jpg", "JPEG", quality=82)
    r = lire()
    r[cle] = f"{cle}.jpg"
    ecrire(r)

def retirer_image(cle):
    p = ASSETS / f"{cle}.jpg"
    if p.exists(): p.unlink()
    r = lire()
    r[cle] = ""
    ecrire(r)

@st.cache_data(show_spinner=False)
def _b64(chemin, mtime):
    return base64.b64encode(pathlib.Path(chemin).read_bytes()).decode()

def _uri(nom, sub=""):
    if not nom:
        return ""
    if store.mysql_actif():
        cle = f"{sub}/{nom}" if sub else nom
        detail = store.media_lire_detail(cle) or store.media_lire_detail(nom)
        if detail:
            octets, mime = detail
            return f"data:{mime};base64," + base64.b64encode(octets).decode("ascii")
    p = ASSETS / sub / nom if sub else ASSETS / nom
    if not p.is_file():
        return ""
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + _b64(str(p), p.stat().st_mtime)

CSS = """
html, body, .stApp{ font-family:"Segoe UI",Arial,sans-serif !important; color:var(--txt); }
header[data-testid="stHeader"]{ background:var(--verre) !important; backdrop-filter:blur(var(--flou)); -webkit-backdrop-filter:blur(var(--flou)); border-bottom:1px solid var(--bord); }
header[data-testid="stHeader"] *{ color:var(--txt) !important; }
#MainMenu, footer{ visibility:hidden; }
.block-container{ padding-top:4.5rem; max-width:1180px; }

[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] span, [data-testid="stMarkdownContainer"] li, [data-testid="stMetricLabel"], [data-testid="stCaptionContainer"], label, .stRadio *, .stToggle *, [data-testid="stExpander"] summary *, h1{ color:var(--txt) !important; }
h2, h3{ color:var(--accent) !important; }

.verre, div[data-testid="stVerticalBlockBorderWrapper"]{ background:var(--verre) !important; backdrop-filter:blur(var(--flou)); -webkit-backdrop-filter:blur(var(--flou)); border:1px solid var(--bord) !important; border-radius:24px; padding:20px; margin-bottom:14px; box-shadow:8px 8px 22px var(--ombre1), -6px -6px 18px var(--ombre2); }
.verre h2{ margin:.2rem 0; } .verre p{ margin:.2rem 0; opacity:.92; }
.entete{ display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
.entete img{ width:64px; height:64px; border-radius:50%; background:#fff; padding:3px; }
.entete h1{ margin:0; font-size:1.9rem; }
.entete h1 span, .eyebrow{ color:var(--accent) !important; }
.eyebrow{ font-weight:700; letter-spacing:.06em; font-size:.78rem; text-transform:uppercase; }
.grand{ font-size:4rem; font-weight:800; line-height:1; color:var(--txt) !important; }
.badge{ display:inline-block; padding:5px 14px; border-radius:20px; font-weight:700; font-size:.85rem; }

.hero{ height:380px; border-radius:24px; position:relative; margin-bottom:14px; overflow:hidden; border:1px solid var(--bord); box-shadow:8px 8px 22px var(--ombre1), -6px -6px 18px var(--ombre2); }
.hero .legende{ position:absolute; left:14px; bottom:14px; padding:8px 14px; border-radius:12px; z-index:10; background:rgba(0,0,0,.55); color:#fff !important; font-weight:700; }

.tuile, div[data-testid="stMetric"], div[data-testid="stDataFrame"], div[data-baseweb="select"] > div, .stButton > button{ background:var(--neo) !important; border:none !important; border-radius:20px; padding:14px; box-shadow:6px 6px 14px var(--ombre1), -5px -5px 12px var(--ombre2) !important; }
.tuile{ text-align:center; margin-bottom:14px; }
.tuile b{ display:block; font-size:2.2rem; margin:4px 0; color:var(--txt) !important; }
.tuile small{ opacity:.85; }
.pt{ display:inline-block; width:12px; height:12px; border-radius:50%; margin-right:6px; }
.stButton > button{ color:var(--txt) !important; font-weight:600; }
div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] *{ color:var(--accent) !important; }
div[data-baseweb="select"] *{ color:var(--txt) !important; }

textarea, input, div[data-testid="stProgress"] > div > div{ background:var(--champ) !important; border:none !important; border-radius:16px; color:var(--txt) !important; box-shadow:inset 5px 5px 10px var(--ombre1), inset -4px -4px 9px var(--ombre2); }
div[data-testid="stProgress"] div[role="progressbar"] > div{ background:var(--accent) !important; }

/* MENUS DÉROULANTS */
[data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="popover"] [data-baseweb="menu"], [data-baseweb="popover"] ul{ background-color: var(--bg_pop) !important; }
[data-baseweb="popover"]{ border: 1px solid var(--bord) !important; box-shadow: 4px 4px 15px var(--ombre1) !important; border-radius: 12px !important; }
[data-baseweb="popover"] li, [data-baseweb="popover"] a, [data-baseweb="popover"] [role="option"]{ background-color: transparent !important; border-radius: 8px !important; }
[data-baseweb="popover"] *{ color: var(--txt) !important; opacity: 1 !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] a:hover, [data-baseweb="popover"] [aria-selected="true"]{ background-color: var(--neo) !important; }

section[data-testid="stSidebar"]{ background:var(--verre) !important; backdrop-filter:blur(var(--flou)); border-right:1px solid var(--bord); }
section[data-testid="stSidebar"] *{ color:var(--txt) !important; }

.fl{ position:fixed; z-index:999; width:76px; height:76px; border-radius:50%; padding:6px; background:rgba(255,255,255,.92); box-shadow:0 10px 28px rgba(0,0,20,.45); animation:fl 6s ease-in-out infinite; }
.fl img{ width:100%; height:100%; border-radius:50%; display:block; }
.f1{ left:18px; bottom:24px; } .f2{ right:18px; bottom:24px; animation-delay:-3s; }
.orb{ position:fixed; border-radius:50%; filter:blur(60px); opacity:.25; z-index:0; pointer-events:none; animation:fl 9s ease-in-out infinite; }
@keyframes fl{ 50%{ transform:translateY(-16px) rotate(4deg); } }
@media(max-width:900px){ .fl{ width:52px; height:52px; } .grand{ font-size:3rem; } .hero{ height:240px; } }
"""

def _une_ligne(texte):
    return " ".join(l.strip() for l in texte.splitlines() if l.strip())

def config():
    icone = ASSETS / "ovg.png"
    st.set_page_config(page_title="SAP-Virunga", page_icon=Image.open(icone) if icone.exists() else "🌋", layout="wide")

# =====================================================================
# LE CERVEAU DE L'ASSISTANT (Il lit les vraies données du site)
# =====================================================================
def generer_reponse(prompt, sites, df):
    p = prompt.lower().strip()
    
    # 1. Salutations
    if any(mot in p for mot in ["bonjour", "salut", "hello", "coucou", "bonsoir"]):
        return "Bonjour ! Je suis l'assistant SAP-Virunga. Vous pouvez me demander 'Quelle est l'alerte actuelle ?', 'Parle-moi de Shasha', ou 'Comment est calculé le score ?'."

    # 2. Questions sur l'alerte actuelle (la plus élevée)
    if any(mot in p for mot in ["actuelle", "actuel", "plus élevé", "plus eleve", "danger", "max"]):
        top = sites.iloc[0]
        return f"L'alerte la plus élevée est actuellement à **{top.site}** avec un niveau **{top.niveau}** (score de {top.score_site:.0f}/100). L'action recommandée est : {ACTION[top.niveau]}."

    # 3. Questions sur un site spécifique
    for _, row in sites.iterrows():
        if row.site.lower() in p:
            return f"Le site **{row.site}** est au niveau **{row.niveau}** avec un score fusionné de {row.score_site:.0f}/100 (confiance {row.confiance} %). L'action requise est : {ACTION[row.niveau]}."

    # 4. Questions sur la méthode / le calcul
    if any(mot in p for mot in ["calcul", "formule", "score", "comment"]):
        return "Le score par canal est calculé avec la formule : **score = min(100, 20 × D)**. Ensuite, pour fusionner par site, on prend le score maximum et on ajoute 5 points par canal supplémentaire dépassant 40."

    # 5. Confiance et Qualité
    if "confiance" in p:
        return "L'indice de confiance est calculé ainsi : **100 × (0,4 × Qualité + 0,3 × Concordance + 0,3 × Persistance)**. Elle est faible en dessous de 50 %, moyenne de 50 à 75 % et élevée au-delà de 75 %."

    # 6. Messages publics (uniquement s'ils sont validés par l'encadreur)
    if any(mot in p for mot in ["message", "public", "diffuser", "sms"]):
        top = sites.iloc[0]
        if top.niveau in ("Orange", "Rouge"):
            m = diffusion.public(top.site, top.niveau)
            if m:
                return f"Le message public validé pour {top.site} est : « {m} »"
            return f"Un message est prévu pour {top.site} ({top.niveau}) mais il n'a pas encore été validé par l'encadreur : il ne peut pas être diffusé."
        return "Actuellement, aucune alerte ne nécessite de message public (niveaux Vert ou Jaune)."

    # 7. Si on ne comprend pas
    return "Je ne suis pas sûr de comprendre. Je suis entraîné sur les données actuelles du site. Essayez de me demander : 'Alerte actuelle', 'Shasha', 'Calcul', ou 'Message public'."


def barre_laterale():
    r = lire()
    with st.sidebar:
        st.markdown("### 🌋 SAP-Virunga")
        
        # --- CONNEXION (comptes chiffrés, voir auth.py) ---
        u = auth.courant()
        if u is None:
            st.markdown("#### 🔐 Connexion")
            with st.form("login"):
                user = st.text_input("Identifiant")
                mdp = st.text_input("Mot de passe", type="password")
                if st.form_submit_button("Se connecter"):
                    essais = st.session_state.get("essais", 0)
                    if essais >= 5:
                        st.error("Trop d'essais. Rechargez la page pour réessayer.")
                    elif auth.connecter(user, mdp):
                        st.session_state.essais = 0
                        st.rerun()
                    else:
                        st.session_state.essais = essais + 1
                        st.error("Identifiants incorrects.")
            st.caption("Visiteur (lecture seule) : `visiteur` / `visiteur`")
        else:
            st.markdown(
                f"<div style='display:flex;gap:10px;align-items:center'>{auth.avatar_html(u, 46)}"
                f"<div><b>{html.escape(u['nom'])}</b><br><small>{html.escape(u['titre'])}</small></div></div>",
                unsafe_allow_html=True)
            if st.button("Se déconnecter"):
                auth.deconnecter()
                st.rerun()

        st.divider()

        # --- PARAMÈTRES VISUELS ---
        jour = st.toggle("☀️ Mode jour", value=(st.session_state.get("mode", r["mode"]) == "jour"))
        
        st.divider()

        # --- ASSISTANT VIRTUEL (Mis à jour) ---
        st.markdown("#### 🤖 Assistant SAP")
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": "Posez-moi une question sur les alertes !"}]
        
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("Votre question..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            
            # ON CHARGE LES DONNÉES EN DIRECT POUR QUE L'ASSISTANT SOIT À JOUR
            sites = charger_fusion()
            df = sites # simplification pour la fonction
            
            reponse = generer_reponse(prompt, sites, df)
            
            st.session_state.messages.append({"role": "assistant", "content": reponse})
            st.chat_message("assistant").write(reponse)

    nv = "jour" if jour else "nuit"
    if nv != st.session_state.get("mode", r["mode"]):
        st.session_state.mode = nv   # propre à cette session : ne change plus l'affichage des autres
        st.rerun()

def theme():
    r = lire()
    T = THEMES.get(st.session_state.get("mode", r["mode"]), THEMES["nuit"])
    fond = f"linear-gradient(135deg,{T['f1']},{T['f2']} 60%,{T['f1']})"
    uri = _uri(r["fond"])
    if uri:
        v = f"rgba({T['rgb']},{r['voile'] / 100})"
        fond = f"linear-gradient({v},{v}), url({uri}) center/cover no-repeat"
    variables = (
        ":root{"
        f"--txt:{T['txt']};--accent:{T['accent']};--verre:{T['verre']};"
        f"--bord:{T['bord']};--neo:{T['neo']};--champ:{T['champ']};--bg_pop:{T['bg_pop']};"
        f"--ombre1:{T['ombre1']};--ombre2:{T['ombre2']};--flou:{r['flou']}px;"
        "}"
        f".stApp,[data-testid=\"stAppViewContainer\"]{{background:{fond} !important;background-attachment:fixed !important;}}"
    )
    st.markdown("<style>" + variables + " " + _une_ligne(CSS) + "</style>", unsafe_allow_html=True)

def entete(titre, sous_titre="Plateforme de veille et d'alerte des risques naturels"):
    img1, img2 = _uri("ovg.png"), _uri("rdc.png")
    flotteurs = ""
    if img1: flotteurs += f'<div class="fl f1"><img src="{img1}"></div>'
    if img2: flotteurs += f'<div class="fl f2"><img src="{img2}"></div>'
    tete_img = f'<img src="{img1}">' if img1 else ""
    mots = titre.split(" ")
    html = (
        '<div class="orb" style="width:340px;height:340px;background:#ECF553;top:-80px;right:-60px"></div>'
        '<div class="orb" style="width:300px;height:300px;background:#F80001;bottom:10%;left:-90px;animation-delay:-4s"></div>'
        + flotteurs + f'<div class="verre entete">{tete_img}'
        f'<div><h1>{mots[0]} <span>{" ".join(mots[1:])}</span></h1><p>{sous_titre}</p></div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def hero(legende):
    dossier_carrousel = ASSETS / "carrousel"
    dossier_carrousel.mkdir(exist_ok=True)
    images = sorted(p for p in dossier_carrousel.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if images:
        n = len(images)
        duree, fondu_s = 6, 1.2            # secondes par image / durée du fondu enchaîné
        total = n * duree
        p1, p2, p3 = fondu_s / total * 100, duree / total * 100, (duree + fondu_s) / total * 100
        css_carrousel = f"""<style>
        .carrousel {{ position: relative; width: 100%; height: 380px; overflow: hidden; background: #0b1a2e; }}
        .carrousel .slide {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; animation: fade {total}s infinite; }}
        .carrousel .slide img {{ width: 100%; height: 100%; object-fit: cover; }}
        @keyframes fade {{ 0% {{ opacity: 0; }} {p1:.3f}% {{ opacity: 1; }} {p2:.3f}% {{ opacity: 1; }} {p3:.3f}% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}
        @media (prefers-reduced-motion: reduce) {{ .carrousel .slide {{ animation: none; }} .carrousel .slide:first-child {{ opacity: 1; }} }}
        """
        for i in range(n): css_carrousel += f".carrousel .slide:nth-child({i+1}) {{ animation-delay: {i * duree}s; }}\n"
        css_carrousel += "</style>"
        html_images = "".join(f'<div class="slide"><img src="{_uri(p.name, sub="carrousel")}"></div>' for p in images)
        st.markdown(css_carrousel, unsafe_allow_html=True)
        st.markdown(f'<div class="hero carrousel">{html_images}<span class="legende">{legende}</span></div>', unsafe_allow_html=True)
        return
    r = lire()
    uri = _uri(r["accueil"]) or _uri(r["fond"])
    fond = f"url({uri}) center/cover" if uri else "linear-gradient(135deg,#2C3C9E,#010860)"
    st.markdown(f'<div class="hero" style="background:{fond}"><span class="legende">{legende}</span></div>', unsafe_allow_html=True)

def badge(nv):
    fond, txt = COULEURS[nv]
    return f'<span class="badge" style="background:{fond};color:{txt} !important">{nv}</span>'

def verre(html): st.markdown(f'<div class="verre">{html}</div>', unsafe_allow_html=True)

def tuile(titre, valeur, legende, nv):
    st.markdown(
        f'<div class="tuile"><span class="pt" style="background:{COULEURS[nv][0]}"></span>'
        f'<b style="font-size:1rem">{titre}</b><b>{valeur}</b><small>{nv} · {legende}</small></div>',
        unsafe_allow_html=True)

def pied():
    verre("<b>Prototype pédagogique</b> · données de démonstration. Aucune alerte officielle.")