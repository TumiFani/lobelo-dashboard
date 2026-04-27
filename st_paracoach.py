import streamlit as st
from pathlib import Path
import pandas as pd
import base64

from sidebar import render_sidebar
from view import render_team_overview, render_performance_analytics
from profiles import render_profiles
from edit import render_edit
from ask_lobelo import render_ask_lobelo


st.set_page_config(page_title="LOBELO", layout="wide")


BASE = Path(__file__).parent
DATA = BASE / "data"


# ---------------- IMAGE LOADER ---------------- #

def load_image(filename):
    file = BASE / filename
    if file.exists():
        return base64.b64encode(file.read_bytes()).decode()
    return ""


START = load_image("start.png")
RUN = load_image("run.png")
FINISH = load_image("finish.png")
ZEBRA = load_image("zebra_bg.png")


# ---------------- DATA LOADER ---------------- #

@st.cache_data
def load_table(name):

    file = DATA / name

    if not file.exists():
        return pd.DataFrame()

    df = pd.read_csv(file)

    for col in ["date", "dob", "start_date", "end_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def load_all():

    training_sessions = load_table("training_sessions.csv")
    performance_tests = load_table("performance_tests.csv")
    competition_results = load_table("competition_results.csv")
    readiness_scores = load_table("readiness_scores.csv")
    coach_notes = load_table("coach_notes.csv")

    return {
        "athletes": load_table("athletes.csv"),

        # Training sessions
        "sessions": training_sessions,
        "training_sessions": training_sessions,

        # Performance tests
        "tests": performance_tests,
        "performance_tests": performance_tests,

        # Competition results
        "results": competition_results,
        "competition_results": competition_results,

        # Readiness scores
        "readiness": readiness_scores,
        "readiness_scores": readiness_scores,

        # Coach notes
        "notes": coach_notes,
        "coach_notes": coach_notes,

        # Injuries
        "injuries": load_table("injuries.csv"),
    }


# ---------------- SIDEBAR HOME LINK ---------------- #

def render_sidebar_home_link():

    st.sidebar.markdown("""
<style>
.lobelo-sidebar-home {
    display:flex;
    align-items:center;
    gap:8px;
    width:100%;
    padding:9px 12px;
    margin:8px 0 12px 0;
    border:1px solid rgba(15,23,42,0.16);
    border-radius:12px;
    color:#0f172a !important;
    background:#ffffff;
    text-decoration:none !important;
    font-size:14px;
    font-weight:650;
    line-height:1;
    box-shadow:0 3px 10px rgba(15,23,42,0.05);
}
.lobelo-sidebar-home:hover {
    background:#f8fafc;
    color:#0f172a !important;
    text-decoration:none !important;
}
.lobelo-sidebar-home svg {
    width:15px;
    height:15px;
    stroke:#0f172a;
    stroke-width:2;
    fill:none;
}
</style>
<a class="lobelo-sidebar-home" href="?page=Landing" target="_self">
    <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 11.5L12 4l9 7.5"></path>
        <path d="M5.5 10.5V20h13v-9.5"></path>
        <path d="M9.5 20v-6h5v6"></path>
    </svg>
    <span>Home</span>
</a>
""", unsafe_allow_html=True)

# ---------------- NON-LANDING PAGE CSS ---------------- #

def app_page_css():

    st.markdown(f"""
<style>

.block-container {{
padding-top:0rem !important;
max-width:100vw !important;
}}

header[data-testid="stHeader"] {{
display:none;
}}

div[data-testid="stToolbar"] {{
display:none;
}}

footer {{
display:none;
}}

.stApp {{
background:#ffffff;
}}

.stApp::before {{
content:"";
position:fixed;
inset:0;
background:url("data:image/png;base64,{ZEBRA}") center/cover no-repeat;
opacity:.34;
z-index:0;
pointer-events:none;
}}

section.main > div,
.block-container {{
position:relative;
z-index:1;
}}

.ask-lobelo-runner {{
position:fixed;
right:42px;
bottom:72px;
width:360px;
height:260px;
background:url("data:image/png;base64,{FINISH}") right bottom no-repeat;
background-size:contain;
opacity:.28;
z-index:0;
pointer-events:none;
}}

</style>
""", unsafe_allow_html=True)


# ---------------- LANDING CSS ---------------- #

def landing_css():

    st.markdown(f"""

<style>

/* REMOVE STREAMLIT TOP SPACE */

.block-container {{
padding:0rem !important;
max-width:100vw !important;
}}

header[data-testid="stHeader"] {{display:none;}}
div[data-testid="stToolbar"] {{display:none;}}
footer {{display:none;}}


/* LANDING WRAPPER */

.landing {{
position:relative;
height:100vh;
overflow:hidden;
top:-8px;
}}


/* ZEBRA BACKGROUND */

.zebra-bg {{
position:absolute;
inset:0;
background:url("data:image/png;base64,{ZEBRA}") center/cover no-repeat;
opacity:.60;
z-index:0;
}}


/* LEFT ATHLETE */

.side-left {{

position:absolute;
left:0;
bottom:0;

width:420px;
height:420px;

background:url("data:image/png;base64,{START}") left bottom no-repeat;
background-size:contain;

filter:grayscale(100%) contrast(1.05);

mask-image:linear-gradient(to right,
rgba(0,0,0,1) 62%,
rgba(0,0,0,0));

opacity:.32;
z-index:2;

}}


/* RIGHT ATHLETE */

.side-right {{

position:absolute;
right:0;
bottom:0;

width:420px;
height:420px;

background:url("data:image/png;base64,{FINISH}") right bottom no-repeat;
background-size:contain;

filter:grayscale(100%) contrast(1.05);

mask-image:linear-gradient(to left,
rgba(0,0,0,1) 62%,
rgba(0,0,0,0));

opacity:.32;
z-index:2;

}}


/* HERO IMAGE */

.hero-wrapper {{
display:flex;
justify-content:center;
margin-top:-10px;
position:relative;
z-index:4;
}}

.hero {{

width:560px;
height:380px;

background:url("data:image/png;base64,{RUN}") center no-repeat;
background-size:contain;

mask-image:
radial-gradient(circle,
rgba(0,0,0,1) 40%,
rgba(0,0,0,0) 100%),
linear-gradient(to bottom,
rgba(0,0,0,1) 90%,
rgba(0,0,0,0) 100%);
mask-composite: intersect;
-webkit-mask-composite: destination-in;

}}


/* HEADER */

.header {{
position:absolute;
top:16px;
left:60px;
font-size:22px;
font-weight:700;
color:#0f172a;
z-index:5;
}}


/* MENU ICON */

.menu {{
position:absolute;
top:40px;
right:40px;
width:26px;
height:16px;
display:flex;
flex-direction:column;
justify-content:space-between;
z-index:5;
}}

.menu span {{
height:2px;
width:26px;
background:#0f172a;
border-radius:2px;
}}


/* TITLE */

.title {{
text-align:center;
font-size:60px;
font-weight:800;
margin-top:-42px;
color:#0f172a;
position:relative;
z-index:4;
}}


/* SUBTITLE */

.subtitle {{
text-align:center;
font-size:17px;
color:#6b7280;
margin-top:-14px;
margin-bottom:10px;
position:relative;
z-index:4;
}}


/* CTA BUTTON */

.cta {{
display:flex;
justify-content:center;
margin-bottom:10px;
position:relative;
z-index:4;
}}

.cta a {{
width:260px;
height:44px;
background:linear-gradient(90deg,#2f56f5,#37b8e6);
border-radius:44px;
font-size:17px;
font-weight:700;
color:white;
text-decoration:none;
display:flex;
align-items:center;
justify-content:center;
box-shadow:0px 10px 24px rgba(47,86,245,0.22);
}}


/* NAV CARDS */

.card-row {{
display:flex;
justify-content:center;
gap:26px;
margin-top:18px;
position:relative;
z-index:4;
}}

/* NAV CARDS — upgraded tiles */

.card a {{

display:inline-flex !important;
align-items:center;
justify-content:center;

padding:14px 26px;

background:rgba(255,255,255,0.55) !important;

border-radius:8px;

font-size:14px;
font-weight:600;

color:#0f172a !important;
text-decoration:none !important;

border:1px solid rgba(0,0,0,0.06);

backdrop-filter:blur(6px);

transition:all .18s ease;
}}

.card a:hover {{

transform:translateY(-3px);

background:white !important;

border:1px solid rgba(37,99,235,0.25);

box-shadow:
0px 12px 28px rgba(37,99,235,0.18);
}}


/* ASK LOBELO BUTTON SHIMMER */

.ask-btn {{
position:relative;
overflow:hidden;
}}

.ask-btn::after {{
content:"";
position:absolute;
top:0;
left:-60%;
width:60%;
height:100%;
background:linear-gradient(
120deg,
transparent,
rgba(55,184,230,0.45),
transparent
);
animation:lobeloShimmer 4.2s infinite;
}}

@keyframes lobeloShimmer {{
0% {{ left:-60%; }}
100% {{ left:120%; }}
}}

.ask-dots {{
letter-spacing:2px;
opacity:.85;
}}

.ask-icon {{
font-size:24px;
margin-left:6px;
position:relative;
top:1px;
}}

</style>

""", unsafe_allow_html=True)


# ---------------- LANDING PAGE ---------------- #

def render_landing():

    landing_css()

    st.markdown("""

<div class="landing">

<div class="zebra-bg"></div>

<div class="side-left"></div>
<div class="side-right"></div>

<div class="header">Welcome</div>

<div class="menu">
<span></span>
<span></span>
<span></span>
</div>

<div class="hero-wrapper">
<div class="hero"></div>
</div>

<div class="title">LOBELO</div>

<div class="subtitle">
Botswana Paralympic Squad Performance Management Platform
</div>

<div class="cta">
<a href="?page=Ask Lobelo" target="_self" class="ask-btn">
<span class="ask-text">Ask Lobelo</span>
<span class="ask-dots">•••</span>
<span class="ask-icon">🤖</span>
</a>
</div>

<div class="card-row">

<div class="card">
<a href="?page=Executive Overview" target="_self">▦ Executive Overview</a>
</div>

<div class="card">
<a href="?page=Performance Analytics" target="_self">▤ Performance Analytics</a>
</div>

<div class="card">
<a href="?page=Athlete Explorer" target="_self">👤 Athlete Explorer</a>
</div>

<div class="card">
<a href="?page=Data Editor" target="_self">🗂 Data Editor</a>
</div>

</div>

</div>

""", unsafe_allow_html=True)


# ---------------- ROUTER ---------------- #

def main():

    data = load_all()

    if "page" not in st.session_state:
        st.session_state.page = "Landing"

    query_page = st.query_params.get("page")

    valid_pages = [
        "Landing",
        "Executive Overview",
        "Performance Analytics",
        "Athlete Explorer",
        "Ask Lobelo",
        "Data Editor",
    ]

    if query_page and query_page in valid_pages:
        st.session_state.page = query_page

    if st.session_state.page == "Landing":
        render_landing()
        return

    app_page_css()

    render_sidebar_home_link()

    sidebar = render_sidebar(data["athletes"])

    if sidebar["page"] and not query_page:
        st.session_state.page = sidebar["page"]
        st.query_params["page"] = sidebar["page"]

    page = st.session_state.page

    if page == "Executive Overview":
        render_team_overview(data, data["athletes"])

    elif page == "Performance Analytics":
        render_performance_analytics(data, data["athletes"])

    elif page == "Athlete Explorer":
        render_profiles(data, data["athletes"])

    elif page == "Ask Lobelo":
        st.markdown('<div class="ask-lobelo-runner"></div>', unsafe_allow_html=True)
        render_ask_lobelo(data, data["athletes"])

    elif page == "Data Editor":
        render_edit(DATA)


if __name__ == "__main__":
    main()