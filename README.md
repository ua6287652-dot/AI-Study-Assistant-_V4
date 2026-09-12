
# AI Study Assistant V4

A persistent, account-based AI Study Assistant built with Streamlit, Supabase and Groq.

## V4 features

- Login / Signup with Supabase Auth
- Permanent cloud database
- User-specific study library
- PDF extraction and private PDF Storage
- Permanent pasted lecture notes
- Previous material loading after login
- AI topic extraction
- RAG-style AI Tutor grounded in saved material
- AI exam/revision notes
- Adaptive MCQ quiz
- Quiz history
- Weak-topic tracking
- Adaptive study planner
- Row Level Security so one user's rows are isolated from another user's rows

## Architecture

Streamlit -> Supabase Auth -> Supabase Database + Storage
                         -> Groq AI

## Setup

### 1. Create a Supabase project

Create a project at Supabase and open SQL Editor.

### 2. Run the database schema

Open `supabase_schema.sql` and run the complete script.

It creates:
- materials
- topics
- quiz_attempts
- weak_topics
- private `study-materials` storage bucket
- RLS policies

### 3. Configure Streamlit Secrets

In local `.streamlit/secrets.toml` or Streamlit Cloud Secrets:

```toml
SUPABASE_URL = "your-supabase-project-url"
SUPABASE_KEY = "your-supabase-publishable-or-anon-key"
GROQ_API_KEY = "your-groq-api-key"
```

Never commit real keys to GitHub.

### 4. Install

```bash
python -m pip install -r requirements.txt
```

### 5. Run

```bash
streamlit run app.py
```

## Important

- Supabase stores the study database permanently, unlike a local SQLite file on an ephemeral Streamlit deployment.
- The original PDF is uploaded to a private Supabase Storage bucket when Storage permissions are configured correctly.
- Extracted text is also stored in the database so the app can answer questions without re-uploading the PDF.
- Scanned/image-only PDFs need OCR; this V4 uses selectable-text PDF extraction.
- For production, consider adding rate limits, audit logs, OCR, document size limits, encrypted secrets, and stronger input validation.

## Suggested GitHub structure

```text
ai-study-assistant-v4/
├── app.py
├── requirements.txt
├── supabase_schema.sql
└── README.md
```


## V4 Fixed — Supabase connection diagnostics

This build normalizes the Supabase URL (including accidentally pasted `/rest/v1/`), trims whitespace, lazy-loads the client, and adds a **Supabase Connection Test** on the login screen. If `[Errno -2] Name or service not known` occurs, the test reports whether the running Streamlit environment can resolve and reach the Supabase Auth endpoint.

Use the root project URL:
`https://YOUR_PROJECT_REF.supabase.co`

Do not use:
`https://YOUR_PROJECT_REF.supabase.co/rest/v1/`
