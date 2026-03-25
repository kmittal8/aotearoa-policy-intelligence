"""
Aotearoa Policy Intelligence — Streamlit Chat UI
OCI GenAI Inference (Hyderabad) + FastAPI Stats NZ tools
"""
import time

import os

import streamlit as st
from dotenv import load_dotenv

import oci_agent

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
PAGE_TITLE = "Aotearoa Policy Intelligence"
GREETING = (
    "Kia ora! I'm the Aotearoa Policy Intelligence assistant.\n\n"
    "I have live access to **914 Stats NZ datasets** — Census 2013/2018/2023, Business "
    "Demography, LEED, Iwi, Justice, and more.\n\n"
    "Ask me any policy question in plain English and I'll find the answer directly "
    "from Stats NZ. Try one of the topics on the left to get started."
)

TOPIC_TILES = [
    ("🏠 Housing", "Compare Māori and Pākehā home ownership rates in 2023"),
    ("👥 Population", "How has Auckland's population changed across the three censuses?"),
    ("💼 Business", "How many businesses were in the agricultural sector in 2022?"),
    ("🌿 Iwi", "What are the largest iwi in New Zealand by population?"),
    ("⚖️ Justice", "How has the NZ prison population changed over the last 5 years?"),
    ("💰 Income", "What is the median income for Māori women aged 25-34 in Wellington?"),
]

# ── Page setup ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="🇳🇿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS — dark theme, subtle oracle-brand accents
st.markdown(
    """
    <style>
    /* Main header */
    .main-header {
        font-size: 1.7rem;
        font-weight: 700;
        color: #e8f0fe;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.85rem;
        color: #9aa0ac;
        margin-bottom: 1.5rem;
    }
    /* Topic tiles */
    div[data-testid="stButton"] > button {
        width: 100%;
        text-align: left;
        background: #1e2a3a;
        border: 1px solid #2d3f55;
        border-radius: 8px;
        color: #c9d6e8;
        padding: 0.5rem 0.75rem;
        margin-bottom: 0.3rem;
        font-size: 0.9rem;
        transition: background 0.15s;
    }
    div[data-testid="stButton"] > button:hover {
        background: #243450;
        border-color: #c74634;
        color: #ffffff;
    }
    /* Chat messages */
    .stChatMessage {
        border-radius: 10px;
    }
    /* Oracle red accent on sidebar header */
    .sidebar-brand {
        color: #c74634;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": GREETING}]
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "prefill" not in st.session_state:
    st.session_state.prefill = ""
if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-brand">Anthropic · Stats NZ</div>', unsafe_allow_html=True)
    st.markdown("### 🇳🇿 Aotearoa Policy Intelligence")
    st.caption("Ask a policy question in plain English.")
    st.divider()

    # API key — hidden if already set via environment variable
    if not os.environ.get("ANTHROPIC_API_KEY"):
        entered_key = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            help="Get your key at console.anthropic.com",
            value=st.session_state.api_key,
        )
        if entered_key != st.session_state.api_key:
            st.session_state.api_key = entered_key
        if not st.session_state.api_key:
            st.warning("Enter your Anthropic API key to start chatting.")
        st.divider()

    st.markdown("**Starter topics**")
    for label, question in TOPIC_TILES:
        if st.button(label, key=f"tile_{label}"):
            st.session_state.prefill = question

    st.divider()

    if st.button("🔄 New conversation"):
        st.session_state.messages = [{"role": "assistant", "content": GREETING}]
        st.session_state.chat_history = []
        st.session_state.prefill = ""
        st.rerun()

    st.divider()
    st.caption("Data: Stats NZ ADE API · 914 live dataflows")
    st.caption("Model: Claude Haiku 4.5 via Anthropic API")

# ── Main area ──────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🇳🇿 Aotearoa Policy Intelligence</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Powered by Anthropic Claude · Live access to 914 Stats NZ datasets</div>',
    unsafe_allow_html=True,
)

# Render chat history
for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── Input handling ─────────────────────────────────────────────────────────────
prefill_value = st.session_state.pop("prefill", "") if st.session_state.get("prefill") else ""

user_input = st.chat_input(
    "Ask a policy question… e.g. 'How has Māori home ownership changed since 2013?'",
    key="chat_input",
)

# Topic tile pre-fill: immediately show in chat and submit
if prefill_value and not user_input:
    user_input = prefill_value

if user_input:
    if not st.session_state.api_key:
        st.warning("Please enter your Anthropic API key in the sidebar first.")
        st.stop()

    # Add user message to display history
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🤖"):
        placeholder = st.empty()
        placeholder.markdown("_Querying Stats NZ datasets…_ ⏳")

        try:
            t0 = time.time()
            answer, st.session_state.chat_history = oci_agent.chat(
                st.session_state.chat_history,
                user_input,
                api_key=st.session_state.api_key,
            )
            elapsed = time.time() - t0

            full_response = f"{answer}\n\n---\n_Retrieved in {elapsed:.1f}s · Source: Stats NZ ADE API_"
            placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as exc:  # noqa: BLE001
            err_msg = (
                f"**Error:**\n\n```\n{exc}\n```\n\n"
                "Check your Anthropic API key in the sidebar."
            )
            placeholder.markdown(err_msg)
            st.session_state.messages.append({"role": "assistant", "content": err_msg})
