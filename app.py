
import io
import json
import re
from datetime import date, datetime, timedelta
from collections import Counter

import streamlit as st
from pypdf import PdfReader
from supabase import create_client

st.set_page_config(page_title="AI Study Assistant V4", page_icon="📚", layout="wide")

# -----------------------------
# Config / clients
# -----------------------------
def get_secret(name):
    try:
        return st.secrets.get(name)
    except Exception:
        return None

SUPABASE_URL = (get_secret("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_KEY = (get_secret("SUPABASE_KEY") or "").strip()
DEFAULT_MODEL = "openai/gpt-oss-120b"

# Accept either the normal project URL or the Data API URL in case it was copied
# from Supabase's Data API page. The Supabase Python client needs the project root.
if SUPABASE_URL.endswith("/rest/v1"):
    SUPABASE_URL = SUPABASE_URL[:-8].rstrip("/")

if "supabase" not in st.session_state:
    st.session_state.supabase = None
if "user" not in st.session_state:
    st.session_state.user = None
if "active_material_id" not in st.session_state:
    st.session_state.active_material_id = None
if "groq_key" not in st.session_state:
    st.session_state.groq_key = get_secret("GROQ_API_KEY") or ""

def sb_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    if st.session_state.supabase is None:
        try:
            st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            raise RuntimeError(
                "Supabase client could not be initialized. "
                f"Check SUPABASE_URL and SUPABASE_KEY. Details: {e}"
            ) from e
    return st.session_state.supabase

def require_config():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase is not configured. Add SUPABASE_URL and SUPABASE_KEY in Streamlit Secrets.")
        st.stop()
    if "/rest/v1" in SUPABASE_URL:
        st.error("SUPABASE_URL must be the project URL without /rest/v1/. Example: https://YOUR_PROJECT_REF.supabase.co")
        st.stop()

require_config()
supabase = sb_client()

# -----------------------------
# Helpers
# -----------------------------
def clean_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    return text

def extract_pdf(file_bytes):
    if not file_bytes:
        raise ValueError("The uploaded PDF is empty.")
    if not file_bytes.lstrip().startswith(b"%PDF"):
        raise ValueError("The selected file does not look like a valid PDF.")
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        txt = page.extract_text() or ""
        pages.append((i, txt))
    full = "\n\n".join(f"[PAGE {p}]\n{t}" for p, t in pages)
    return full, len(pages), sum(len(t.split()) for _, t in pages)

def chunk_text(text, size=900, overlap=120):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(0, end - overlap)
    return chunks

def retrieve(text, query, k=5):
    chunks = chunk_text(text)
    q = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", query.lower()))
    scored = []
    for c in chunks:
        words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", c.lower()))
        score = len(q & words)
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]

def groq_chat(api_key, prompt, system="You are a helpful study assistant.", temperature=0.2):
    if not api_key:
        raise ValueError("Groq API key is missing.")
    from groq import Groq
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content

# -----------------------------
# Auth
# -----------------------------
def sign_in(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        return True, "Login successful."
    except Exception as e:
        return False, supabase_connection_error(e)

def sign_up(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if getattr(res, "session", None):
            st.session_state.user = res.user
            return True, "Account created and logged in."
        return True, "Account created. Check your email if confirmation is enabled in Supabase."
    except Exception as e:
        return False, supabase_connection_error(e)

def sign_out():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.session_state.active_material_id = None
    st.rerun()

require_config()

if not st.session_state.user:
    st.title("📚 AI Study Assistant V4")
    st.caption("Persistent cloud learning workspace with AI Tutor, quizzes, weak-topic tracking and study planning.")

    login_tab, signup_tab = st.tabs(["Login", "Create Account"])
    with login_tab:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", type="primary", use_container_width=True):
            ok, msg = sign_in(email, password)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with signup_tab:
        email2 = st.text_input("Email", key="signup_email")
        p1 = st.text_input("Password", type="password", key="signup_p1")
        p2 = st.text_input("Confirm Password", type="password", key="signup_p2")
        if st.button("Create Account", use_container_width=True):
            if p1 != p2:
                st.error("Passwords do not match.")
            elif len(p1) < 6:
                st.error("Use at least 6 characters.")
            else:
                ok, msg = sign_up(email2, p1)
                if ok:
                    st.success(msg)
                    if st.session_state.user:
                        st.rerun()
                else:
                    st.error(msg)

    st.divider()
    with st.expander("🔧 Supabase Connection Test"):
        st.caption(f"Configured Project URL: {SUPABASE_URL or 'Not configured'}")
        if st.button("Test Supabase Connection", use_container_width=True):
            try:
                # Auth settings endpoint is public and does not require a logged-in user.
                import requests
                r = requests.get(
                    f"{SUPABASE_URL}/auth/v1/settings",
                    headers={"apikey": SUPABASE_KEY},
                    timeout=10,
                )
                if 200 <= r.status_code < 300:
                    st.success("Supabase connection is working. The signup issue is not DNS/network related.")
                else:
                    st.error(f"Supabase responded with HTTP {r.status_code}: {r.text[:500]}")
            except Exception as e:
                st.error(supabase_connection_error(e))

    st.info("Your study data is stored per account in Supabase. Do not upload confidential documents you are not authorized to store.")
    st.stop()

user_id = st.session_state.user.id

# -----------------------------
# Database functions
# -----------------------------
def user_materials():
    return supabase.table("materials").select("*").eq("user_id", user_id).order("created_at", desc=True).execute().data or []

def get_material(mid):
    rows = supabase.table("materials").select("*").eq("id", mid).eq("user_id", user_id).limit(1).execute().data or []
    return rows[0] if rows else None

def save_material(name, text, pages=0, words=0, storage_path=None):
    data = {
        "user_id": user_id,
        "name": name,
        "pages": pages,
        "words": words,
        "text_content": text,
        "storage_path": storage_path,
    }
    res = supabase.table("materials").insert(data).execute()
    return res.data[0]["id"]

def delete_material(mid, storage_path=None):
    if storage_path:
        try:
            supabase.storage.from_("study-materials").remove([storage_path])
        except Exception:
            pass
    supabase.table("materials").delete().eq("id", mid).eq("user_id", user_id).execute()
    supabase.table("topics").delete().eq("material_id", mid).eq("user_id", user_id).execute()
    supabase.table("quiz_attempts").delete().eq("material_id", mid).eq("user_id", user_id).execute()

def save_topics(mid, topics):
    if not topics:
        return
    supabase.table("topics").delete().eq("material_id", mid).eq("user_id", user_id).execute()
    rows = [
        {"user_id": user_id, "material_id": mid, "name": t.get("name","Untitled"), "description": t.get("description","")}
        for t in topics
    ]
    supabase.table("topics").insert(rows).execute()

def get_topics(mid=None):
    q = supabase.table("topics").select("*").eq("user_id", user_id)
    if mid:
        q = q.eq("material_id", mid)
    return q.order("created_at").execute().data or []

def save_quiz(topic, score, total, difficulty, material_id=None):
    supabase.table("quiz_attempts").insert({
        "user_id": user_id, "material_id": material_id,
        "topic": topic, "score": score, "total": total,
        "difficulty": difficulty
    }).execute()
    pct = round((score / total) * 100, 1) if total else 0
    existing = supabase.table("weak_topics").select("*").eq("user_id", user_id).eq("topic", topic).limit(1).execute().data or []
    if existing:
        row = existing[0]
        attempts = int(row.get("attempts", 0)) + 1
        # running average
        new_score = round(((float(row.get("score", 0)) * (attempts - 1)) + pct) / attempts, 1)
        supabase.table("weak_topics").update({"score": new_score, "attempts": attempts, "updated_at": datetime.utcnow().isoformat()}).eq("id", row["id"]).eq("user_id", user_id).execute()
    else:
        supabase.table("weak_topics").insert({
            "user_id": user_id, "topic": topic, "score": pct, "attempts": 1
        }).execute()

def dashboard():
    attempts = supabase.table("quiz_attempts").select("*").eq("user_id", user_id).execute().data or []
    weak = supabase.table("weak_topics").select("*").eq("user_id", user_id).order("score").execute().data or []
    mats = user_materials()
    total_q = sum(int(x.get("total", 0)) for x in attempts)
    total_correct = sum(int(x.get("score", 0)) for x in attempts)
    avg = round(total_correct / total_q * 100, 1) if total_q else 0
    return mats, attempts, weak, avg

# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.title("AI Study Assistant V4")
st.sidebar.write(f"👤 {st.session_state.user.email}")

if st.sidebar.button("Logout", use_container_width=True):
    sign_out()

st.sidebar.divider()
st.sidebar.subheader("AI Settings")
groq_input = st.sidebar.text_input("Groq API Key", value=st.session_state.groq_key, type="password", help="For local testing only. Prefer Streamlit Secrets for deployment.")
if groq_input:
    st.session_state.groq_key = groq_input

st.sidebar.divider()
st.sidebar.subheader("Study Library")

uploaded = st.sidebar.file_uploader("Upload PDF", type=["pdf"])
if st.sidebar.button("Save Uploaded PDF", use_container_width=True):
    if not uploaded:
        st.sidebar.warning("Select a PDF first.")
    else:
        try:
            data = uploaded.getvalue()
            text, pages, words = extract_pdf(data)
            if not text.strip():
                raise ValueError("No selectable text was found. This version needs OCR for scanned-image PDFs.")
            storage_path = f"{user_id}/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{re.sub(r'[^A-Za-z0-9_.-]', '_', uploaded.name)}"
            try:
                supabase.storage.from_("study-materials").upload(
                    storage_path, data, {"content-type": "application/pdf", "upsert": "false"}
                )
            except Exception as e:
                storage_path = None
                st.sidebar.warning(f"Cloud PDF file upload failed, but extracted text will still be saved. {e}")
            mid = save_material(uploaded.name, text, pages, words, storage_path)
            st.session_state.active_material_id = mid
            st.sidebar.success("PDF and study text saved.")
        except Exception as e:
            st.sidebar.error(str(e))

paste = st.sidebar.text_area("Or paste lecture notes", height=140)
if st.sidebar.button("Save Pasted Notes", use_container_width=True):
    if not paste.strip():
        st.sidebar.warning("Paste some notes first.")
    else:
        mid = save_material(f"Pasted Notes — {datetime.now().strftime('%Y-%m-%d %H:%M')}", paste.strip(), 0, len(paste.split()), None)
        st.session_state.active_material_id = mid
        st.sidebar.success("Notes saved permanently to your account.")

mats = user_materials()
if mats:
    labels = {m["id"]: f'{m["name"]} — {m.get("words",0)} words' for m in mats}
    ids = list(labels.keys())
    current_index = ids.index(st.session_state.active_material_id) if st.session_state.active_material_id in ids else 0
    selected_id = st.sidebar.selectbox("Previous saved material", ids, index=current_index, format_func=lambda x: labels[x])
    if st.sidebar.button("Load Selected Material", use_container_width=True):
        st.session_state.active_material_id = selected_id
        st.rerun()
else:
    st.sidebar.caption("No saved materials yet.")

active = get_material(st.session_state.active_material_id) if st.session_state.active_material_id else (mats[0] if mats else None)
if active:
    st.session_state.active_material_id = active["id"]

# -----------------------------
# Main
# -----------------------------
st.title("📚 AI Study Assistant V4")
st.caption("Login → save your material → study with grounded AI → take adaptive quizzes → track weaknesses → plan your revision.")

if not active:
    st.info("Start by uploading a PDF or saving lecture notes from the sidebar.")
    st.stop()

st.success(f"Active material: **{active['name']}**")
tabs = st.tabs(["Dashboard", "Library", "Topics", "AI Tutor", "AI Notes", "Adaptive Quiz", "Study Planner"])

# Dashboard
with tabs[0]:
    mats, attempts, weak, avg = dashboard()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saved Materials", len(mats))
    c2.metric("Quiz Attempts", len(attempts))
    c3.metric("Overall Score", f"{avg}%")
    c4.metric("Weak Topics", len([w for w in weak if float(w.get("score",0)) < 70]))

    st.subheader("Recent Quiz History")
    if attempts:
        st.dataframe([
            {
                "Topic": a.get("topic"),
                "Score": f"{a.get('score',0)}/{a.get('total',0)}",
                "Difficulty": a.get("difficulty"),
                "Date": a.get("created_at","")[:19]
            } for a in attempts[:15]
        ], use_container_width=True)
    else:
        st.write("No quiz attempts yet.")

    if weak:
        st.subheader("Weakest Topics")
        st.dataframe([
            {"Topic": w.get("topic"), "Average Score": f"{w.get('score',0)}%", "Attempts": w.get("attempts",0)}
            for w in weak[:10]
        ], use_container_width=True)

# Library
with tabs[1]:
    st.subheader("Your Persistent Study Library")
    for m in mats:
        with st.expander(f"{m['name']} · {m.get('words',0)} words"):
            st.write(f"Pages: {m.get('pages',0)}")
            st.write(f"Created: {str(m.get('created_at',''))[:19]}")
            preview = (m.get("text_content") or "")[:1000]
            st.text_area("Preview", preview, height=160, disabled=True, key=f"preview_{m['id']}")
            col1, col2 = st.columns(2)
            if col1.button("Make Active", key=f"active_{m['id']}"):
                st.session_state.active_material_id = m["id"]
                st.rerun()
            if col2.button("Delete", key=f"delete_{m['id']}"):
                delete_material(m["id"], m.get("storage_path"))
                if st.session_state.active_material_id == m["id"]:
                    st.session_state.active_material_id = None
                st.rerun()

# Topics
with tabs[2]:
    st.subheader("Automatic Topic Extraction")
    existing_topics = get_topics(active["id"])
    if st.button("Extract & Save Topics with AI", type="primary"):
        try:
            prompt = f"""Analyze these study notes and return ONLY valid JSON.
Schema: {{"topics":[{{"name":"...","description":"..."}}]}}
Extract 5-12 meaningful academic topics. Do not invent topics.
NOTES:
{active['text_content'][:18000]}"""
            data = json.loads(clean_json(groq_chat(st.session_state.groq_key, prompt)))
            save_topics(active["id"], data.get("topics", []))
            st.success("Topics saved to your cloud database.")
            st.rerun()
        except Exception as e:
            st.error(str(e))
    existing_topics = get_topics(active["id"])
    if existing_topics:
        for t in existing_topics:
            st.markdown(f"**{t['name']}** — {t.get('description','')}")
    else:
        st.info("No topics saved yet.")

# AI Tutor
with tabs[3]:
    st.subheader("AI Tutor — RAG Grounded")
    question = st.text_input("Ask a question about your active material")
    if st.button("Ask AI Tutor", type="primary"):
        if not question.strip():
            st.warning("Enter a question.")
        else:
            try:
                contexts = retrieve(active["text_content"], question, 5)
                if not contexts:
                    st.warning("I could not find relevant context in your material. Try keywords used in the notes.")
                else:
                    context = "\n\n---\n\n".join(contexts)
                    prompt = f"""Answer the learner's question using ONLY the supplied study context.
If the answer is not supported by the context, say that it is not available in the material.
Give a clear explanation and mention the relevant page markers when present.

QUESTION:
{question}

STUDY CONTEXT:
{context}"""
                    ans = groq_chat(st.session_state.groq_key, prompt, system="You are a careful tutor. Stay grounded in the supplied study context.")
                    st.markdown(ans)
                    st.caption("Sources: retrieved chunks from the active saved material.")
            except Exception as e:
                st.error(str(e))

# Notes
with tabs[4]:
    st.subheader("AI Exam Notes")
    if st.button("Generate Revision Notes", type="primary"):
        try:
            prompt = f"""Create exam-ready revision notes from the study material below.
Use headings, bullet points, definitions, key ideas, and a short last-minute revision checklist.
Do not add facts that are not in the material.

MATERIAL:
{active['text_content'][:22000]}"""
            st.markdown(groq_chat(st.session_state.groq_key, prompt, temperature=0.1))
        except Exception as e:
            st.error(str(e))

# Quiz
with tabs[5]:
    st.subheader("Adaptive MCQ Quiz")
    topics = get_topics(active["id"])
    topic_names = [t["name"] for t in topics] or ["General"]
    selected_topic = st.selectbox("Topic", topic_names)
    difficulty = st.select_slider("Difficulty", options=["Beginner", "Intermediate", "Advanced"], value="Intermediate")
    n_questions = st.slider("Questions", 3, 10, 5)

    if st.button("Generate Quiz", type="primary"):
        try:
            context = active["text_content"][:18000]
            if selected_topic != "General":
                matches = retrieve(context, selected_topic, 6)
                if matches:
                    context = "\n\n".join(matches)
            prompt = f"""Create exactly {n_questions} single-answer MCQs from the study context.
Topic: {selected_topic}
Difficulty: {difficulty}
Return ONLY valid JSON:
{{"questions":[{{"question":"...","options":["A","B","C","D"],"answer":0,"explanation":"..."}}]}}
Rules: exactly 4 options; answer is 0-3; one correct answer; stay grounded in the context.

CONTEXT:
{context}"""
            quiz = json.loads(clean_json(groq_chat(st.session_state.groq_key, prompt)))
            st.session_state.quiz = quiz.get("questions", [])
            st.session_state.quiz_topic = selected_topic
            st.session_state.quiz_difficulty = difficulty
            st.session_state.quiz_answers = {}
        except Exception as e:
            st.error(str(e))

    quiz = st.session_state.get("quiz", [])
    if quiz:
        with st.form("quiz_form"):
            answers = {}
            for i, q in enumerate(quiz):
                answers[i] = st.radio(f"{i+1}. {q['question']}", q["options"], key=f"quiz_{i}")
            submitted = st.form_submit_button("Submit Quiz")
        if submitted:
            score = 0
            for i, q in enumerate(quiz):
                if answers[i] == q["options"][q["answer"]]:
                    score += 1
            st.session_state.quiz_result = (score, len(quiz))
            save_quiz(st.session_state.quiz_topic, score, len(quiz), st.session_state.quiz_difficulty, active["id"])
            st.success(f"Score: {score}/{len(quiz)}")
            for i, q in enumerate(quiz):
                chosen = answers[i]
                correct = q["options"][q["answer"]]
                if chosen == correct:
                    st.write(f"**Q{i+1}: Correct** — {q.get('explanation','')}")
                else:
                    st.write(f"**Q{i+1}: Review** — Correct answer: {correct}. {q.get('explanation','')}")

# Planner
with tabs[6]:
    st.subheader("Adaptive Study Planner")
    exam_date = st.date_input("Exam date", value=date.today() + timedelta(days=14), min_value=date.today())
    hours = st.number_input("Study hours available per day", min_value=0.5, max_value=16.0, value=2.0, step=0.5)
    if st.button("Generate Adaptive Plan", type="primary"):
        try:
            weak = supabase.table("weak_topics").select("*").eq("user_id", user_id).order("score").execute().data or []
            topics = get_topics(active["id"])
            topic_text = "\n".join(f"- {t['name']}: {t.get('description','')}" for t in topics)
            weak_text = "\n".join(f"- {w['topic']}: {w.get('score',0)}% average" for w in weak[:10]) or "- No weak-topic history yet"
            days = max(1, (exam_date - date.today()).days)
            prompt = f"""Create a realistic adaptive study plan.
Exam in {days} days. Available time: {hours} hours/day.
Prioritize weak topics, then cover remaining topics, then revision and practice.
Return a day-by-day plan with time blocks and measurable tasks.

TOPICS:
{topic_text}

WEAK TOPICS:
{weak_text}"""
            st.markdown(groq_chat(st.session_state.groq_key, prompt, temperature=0.2))
        except Exception as e:
            st.error(str(e))

st.divider()
st.caption("V4 architecture: Streamlit + Supabase Auth/Database/Storage + Groq. User data is isolated by auth.uid() through Row Level Security.")
