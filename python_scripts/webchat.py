import streamlit as st
import requests
import json
from pathlib import Path
import datetime

# ------------------------------------------------
# Page config
# ------------------------------------------------
st.set_page_config(
    page_title="ChatGPT-style AI",
    page_icon="🤖",
    layout="wide"
)

# ------------------------------------------------
# ChatGPT-style CSS
# ------------------------------------------------
st.markdown("""
<style>
/* App background */
html, body, [class*="stApp"] {
    background-color: #0b0f19;
    color: #e5e7eb;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #020617;
    border-right: 1px solid #1f2937;
}

/* Chat container */
.stChatMessage {
    padding: 16px;
    border-radius: 10px;
    margin-bottom: 12px;
    max-width: 900px;
}

/* User bubble */
[data-testid="stChatMessage-user"] {
    background-color: #1e293b;
    margin-left: auto;
}

/* Assistant bubble */
[data-testid="stChatMessage-assistant"] {
    background-color: #020617;
    border: 1px solid #1f2937;
}

/* Input bar */
.stChatInput {
    position: sticky;
    bottom: 0;
    background: #020617;
    border-top: 1px solid #1f2937;
    padding-top: 12px;
}

/* Remove Streamlit junk */
header, footer {
    visibility: hidden;
}

/* Scrollbar (desktop only) */
::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-thumb {
    background: #334155;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------
# Sidebar (ChatGPT-like)
# ------------------------------------------------
with st.sidebar:
    st.markdown("## 🤖 Your AI")
    st.caption("Local • Private • Yours")

    st.divider()

    model_name = st.selectbox(
        "Model",
        ["mistral:7b-instruct-q4_0", "phi3:mini", "tinyllama"],
        index=0
    )

    temperature = st.slider("Creativity", 0.0, 1.0, 0.3, 0.1)

    if st.button("➕ New chat", use_container_width=True):
        st.session_state.history = []

# ------------------------------------------------
# Paths
# ------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
MEMORY_FILE = DATA_DIR / "memory.txt"

def load_memory():
    if MEMORY_FILE.exists():
        return MEMORY_FILE.read_text()
    return ""

def save_memory(text):
    with open(MEMORY_FILE, "a") as f:
        f.write(text + "\n")

persistent_memory = load_memory()

# ------------------------------------------------
# Session state
# ------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []

# ------------------------------------------------
# Chat display
# ------------------------------------------------
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ------------------------------------------------
# Input
# ------------------------------------------------
user_input = st.chat_input("Message your AI…")

if user_input:
    st.session_state.history.append(
        {"role": "user", "content": user_input}
    )
    with st.chat_message("user"):
        st.markdown(user_input)

    conversation = ""
    for msg in st.session_state.history[-8:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        conversation += f"{role}: {msg['content']}\n"

    SYSTEM_PROMPT = (
        "You are a highly intelligent, helpful AI assistant. "
        "Answer clearly, accurately, and concisely. "
        "Do not repeat the user's input."
    )

    prompt = (
        SYSTEM_PROMPT
        + "\n\nMemory:\n"
        + persistent_memory[-1000:]
        + "\n\nConversation:\n"
        + conversation
        + "Assistant:"
    )

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False
                },
                timeout=300
            )

            reply = ""
            for line in response.text.splitlines():
                if line.strip():
                    data = json.loads(line)
                    reply += data.get("response", "")

            reply = reply.strip()
            st.markdown(reply)

    st.session_state.history.append(
        {"role": "assistant", "content": reply}
    )

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    save_memory(f"[{timestamp}] User: {user_input}")
    save_memory(f"[{timestamp}] Assistant: {reply}")
