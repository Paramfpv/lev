# app.py
import streamlit as st
import requests
from datetime import datetime
import json

# ---------- CONFIG ----------
API_BASE = "http://localhost:8000"   # change if API runs elsewhere
st.set_page_config(page_title="LEV Chat", layout="wide", initial_sidebar_state="expanded")

# ---------- HELPERS ----------
def try_rerun_if_available():
    fn = getattr(st, "experimental_rerun", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass

def api_post(path, json_payload):
    try:
        r = requests.post(API_BASE + path, json=json_payload, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def api_get(path):
    try:
        r = requests.get(API_BASE + path, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# ---------- SESSION INIT ----------
if "page" not in st.session_state:
    st.session_state.page = "auth"  # 'auth' or 'chat'
if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []
if "prompt" not in st.session_state:
    st.session_state.prompt = ""
if "_last_action_msg" not in st.session_state:
    st.session_state._last_action_msg = None

# ---------- STYLES (aesthetic) ----------
st.markdown(
    """
    <style>
    .chat-container { max-width: 900px; margin: 0 auto; }
    .msg-user { background: linear-gradient(120deg,#e0f2ff,#d9f7ff); padding:12px; border-radius:12px; margin:8px 0; }
    .msg-assistant { background: linear-gradient(120deg,#f6f6f9,#eef2ff); padding:12px; border-radius:12px; margin:8px 0; }
    .sidebar .block-container { padding-top: 1rem; }
    .title { font-weight:700; font-size:20px; }
    .muted { color: #6b7280; font-size:12px; }
    .topbar { display:flex; align-items:center; justify-content:space-between; gap:10px; }
    .brand { font-weight:700; font-size:18px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- CALLBACKS ----------
def perform_login(is_register=False):
    email = st.session_state.get("_auth_email", "").strip()
    pwd = st.session_state.get("_auth_pwd", "")
    if not email or not pwd:
        st.session_state._last_action_msg = "Email & password required."
        try_rerun_if_available()
        return
    path = "/register" if is_register else "/login"
    res = api_post(path, {"email": email, "password": pwd})
    if res.get("error"):
        st.session_state._last_action_msg = f"Auth error: {res['error']}"
    else:
        uid = res.get("user_id") or (res.get("user") or {}).get("id")
        if uid:
            st.session_state.user = {"user_id": uid, "email": res.get("email", email)}
            st.session_state.page = "chat"
            # fetch history
            hist = api_get(f"/history/{uid}")
            if not hist.get("error"):
                st.session_state.history = hist.get("history", [])
            st.session_state._last_action_msg = None
        else:
            st.session_state._last_action_msg = "Auth succeeded but no user_id returned."
    try_rerun_if_available()

def perform_logout():
    st.session_state.user = None
    st.session_state.messages = []
    st.session_state.history = []
    st.session_state.page = "auth"
    # clear auth fields too
    st.session_state["_auth_email"] = ""
    st.session_state["_auth_pwd"] = ""
    try_rerun_if_available()

def send_callback():
    prompt_text = st.session_state.get("prompt", "").strip()
    if not prompt_text:
        st.session_state._last_action_msg = "Type a question."
        try_rerun_if_available()
        return

    ts = datetime.utcnow().isoformat()
    st.session_state.messages.append({"role": "user", "text": prompt_text, "ts": ts})

    payload = {"question": prompt_text}
    if st.session_state.user:
        payload["user_id"] = st.session_state.user["user_id"]

    res = api_post("/chat", payload)
    if res.get("error"):
        st.session_state.messages.append({"role": "assistant", "text": "Error: " + str(res["error"]), "ts": datetime.utcnow().isoformat()})
    else:
        ans = res.get("answer") or res.get("data") or str(res)
        st.session_state.messages.append({"role": "assistant", "text": ans, "ts": datetime.utcnow().isoformat()})

    st.session_state.prompt = ""
    st.session_state._last_action_msg = None
    try_rerun_if_available()

def clear_callback():
    st.session_state.messages = []
    try_rerun_if_available()

def new_chat_callback():
    # Save current chat to history (if any messages)
    if not st.session_state.messages:
        st.session_state._last_action_msg = "No messages to save."
        try_rerun_if_available()
        return

    # Create a summary / title for history entry: first user message or snippet
    first_user = next((m for m in st.session_state.messages if m["role"] == "user"), None)
    title = (first_user["text"][:120] + "...") if first_user else "Chat " + datetime.utcnow().isoformat()
    entry = {
        "id": f"local-{datetime.utcnow().timestamp()}",
        "question": title,
        "answer": "\n\n".join([f"{m['role'].upper()}: {m['text']}" for m in st.session_state.messages]),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # push locally
    st.session_state.history.insert(0, entry)

    # try to persist to backend (POST /history or /save_history)
    if st.session_state.user:
        uid = st.session_state.user["user_id"]
        payload = {"user_id": uid, "question": title, "answer": entry["answer"], "timestamp": entry["timestamp"]}
        # attempt /history (POST) then fallback to /save_history
        res = api_post("/history", payload)
        if res.get("error"):
            res2 = api_post("/save_history", payload)
            if res2.get("error"):
                # fail gracefully, don't block new chat
                st.session_state._last_action_msg = "Saved locally; backend save failed."
            else:
                st.session_state._last_action_msg = "New chat saved."
        else:
            st.session_state._last_action_msg = "New chat saved."
    else:
        st.session_state._last_action_msg = "Saved locally (login to persist)."

    # clear chat
    st.session_state.messages = []
    try_rerun_if_available()

def load_history_item(item_id):
    # find item by id and load messages (best-effort parsing)
    item = next((h for h in st.session_state.history if h["id"] == item_id or str(h.get("id")) == str(item_id)), None)
    if not item:
        st.session_state._last_action_msg = "History item not found."
        try_rerun_if_available()
        return
    # naive split for display: trust the stored "answer" contains alternating ROLE: text
    lines = item.get("answer", "").splitlines()
    msgs = []
    for ln in lines:
        if ln.startswith("USER:"):
            msgs.append({"role": "user", "text": ln[5:].strip(), "ts": item.get("timestamp")})
        elif ln.startswith("ASSISTANT:"):
            msgs.append({"role": "assistant", "text": ln[10:].strip(), "ts": item.get("timestamp")})
        else:
            # append to last message if exists
            if msgs:
                msgs[-1]["text"] += "\n" + ln
    st.session_state.messages = msgs
    try_rerun_if_available()

# ---------- LAYOUT ----------
# Top bar
st.markdown(
    """
    <div class="topbar">
      <div class="brand">LEV Chat</div>
      <div class="muted">AI assistant • clean, minimal</div>
    </div>
    <hr/>
    """,
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.markdown("### Controls")
    if st.session_state.user and st.session_state.page == "chat":
        st.success(f"Signed in: {st.session_state.user.get('email')}")
        st.button("Logout", on_click=perform_logout)
        st.markdown("---")
        st.button("New Chat", on_click=new_chat_callback)
        st.button("Clear Chat", on_click=clear_callback)
        st.markdown("---")
        st.markdown("#### Recent chats")
        if st.session_state.history:
            # compact list: click to load
            for it in st.session_state.history:
                label = (it.get("question") or "")[:60]
                if st.button(label, key=f"load_{it['id']}"):
                    load_history_item(it["id"])
        else:
            st.info("No history yet.")
    else:
        # Auth page sidebar (minimal)
        st.write("You are not signed in.")
        if st.button("Go to Login/Register"):
            st.session_state.page = "auth"
            try_rerun_if_available()

# Page content
if st.session_state.page == "auth":
    st.markdown("## Welcome — please login or register")
    cols = st.columns(2)
    with cols[0]:
        st.markdown("### Login")
        st.text_input("Email", key="_auth_email")
        st.text_input("Password", type="password", key="_auth_pwd")
        st.button("Login", on_click=lambda: perform_login(False))
    with cols[1]:
        st.markdown("### Register")
        st.text_input("Register Email", key="_reg_email")
        st.text_input("Register Password", type="password", key="_reg_pwd")
        # Hook register fields into the shared auth callback by copying into _auth_* keys when user clicks register
        def reg_wrapper():
            st.session_state["_auth_email"] = st.session_state.get("_reg_email", "")
            st.session_state["_auth_pwd"] = st.session_state.get("_reg_pwd", "")
            perform_login(is_register=True)
        st.button("Register", on_click=reg_wrapper)

    st.markdown("---")
    st.caption("Tip: register then login. After login you'll see your chats in the sidebar.")

else:
    # Chat UI
    col_main, col_right = st.columns([3, 1])
    with col_main:
        st.markdown("### Chat")
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        if not st.session_state.messages:
            st.info("No messages yet. Use the box below to start.")
        for m in st.session_state.messages:
            if m.get("role") == "user":
                st.markdown(f'<div class="msg-user"><strong>You</strong><div style="font-size:13px; margin-top:6px;">{m["text"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="msg-assistant"><strong>Assistant</strong><div style="font-size:13px; margin-top:6px;">{m["text"]}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Action bar: prompt + buttons (callbacks)
        st.text_area("Ask something...", key="prompt", height=110)
        row = st.columns([1,1,1])
        row[0].button("Send", on_click=send_callback)
        row[1].button("New Chat (Save)", on_click=new_chat_callback)
        row[2].button("Save Locally", on_click=lambda: st.session_state.history.insert(0, {
            "id": f"local-{datetime.utcnow().timestamp()}",
            "question": (st.session_state.prompt or "manual-save")[:120],
            "answer": "\n\n".join([f"{m['role'].upper()}: {m['text']}" for m in st.session_state.messages]),
            "timestamp": datetime.utcnow().isoformat()
        }))

    with col_right:
        st.markdown("### Session")
        if st.session_state.user:
            st.write(f"Signed in as: **{st.session_state.user.get('email')}**")
            st.button("Logout", on_click=perform_logout)
        else:
            st.info("You're using guest mode. Register to persist chats.")
        st.markdown("---")
        st.markdown("### Quick tips")
        st.write("- Keep prompts short and clear.")
        st.write("- Use 'New Chat' to archive the current conversation.")
        st.markdown("---")
        st.markdown("### History preview")
        if st.session_state.history:
            for h in st.session_state.history[:5]:
                st.markdown(f"**{(h.get('question') or '')[:40]}**")
                st.markdown(f"<div class='muted'>{h.get('timestamp','')}</div>", unsafe_allow_html=True)
        else:
            st.write("No saved chats.")

# show any last action message
if st.session_state.get("_last_action_msg"):
    st.warning(st.session_state["_last_action_msg"])
