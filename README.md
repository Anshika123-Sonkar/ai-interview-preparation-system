# InterviewIQ — AI Interview Preparation & Evaluation System

A student-built web application for interview practice, answer feedback, interview history, and resume skill extraction.

> **Educational project only.** Scores are practice feedback, not a validated measure of ability and must not be used to make hiring decisions.

## Features

- FastAPI backend with responsive HTML/CSS templates
- Sign-up, login, password hashing, and session-based authentication
- Technical, HR, and behavioral question bank
- Answer report with score, strengths, and improvement suggestions
- Optional OpenAI-powered structured feedback
- Local heuristic feedback when no API key is configured
- PDF/TXT resume text extraction and keyword-based skill detection
- Dashboard, interview history, and `/api/health` endpoint
- SQLite database created locally at runtime

## Tech stack

Python · FastAPI · SQLite · Jinja2 · HTML · CSS · JavaScript · pypdf · optional OpenAI API

## Run locally (Windows / PowerShell)

1. Extract the ZIP and open the `ai_interview_system` folder in VS Code.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this for the current terminal only:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

3. Install packages:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Start the server:

   ```powershell
   python -m uvicorn app:app --reload
   ```

5. Open `http://127.0.0.1:8000` and create a demo account.

Stop the server with `Ctrl+C`.

## Optional: enable OpenAI feedback

Without an API key, the app uses a simple local heuristic. To enable optional LLM feedback, set environment variables in PowerShell **before** starting the server:

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_MODEL="gpt-4o-mini"
$env:SESSION_SECRET="use-a-long-random-secret"
python -m uvicorn app:app --reload
```

Never commit API keys or real secrets. API calls may incur charges. If the API is unavailable, the app falls back to local feedback. Keep `.env` and other secrets out of GitHub.

## Project structure

```text
ai_interview_system/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── static/
│   └── style.css
└── templates/
    ├── base.html
    ├── index.html
    ├── signup.html
    ├── login.html
    ├── dashboard.html
    ├── interview.html
    ├── report.html
    ├── history.html
    └── resume.html
```

The `data/` directory is generated locally and is intentionally excluded from GitHub because it may contain a database and private resume data.

## Main routes

- `/` — landing page
- `/signup`, `/login`, `/logout`
- `/dashboard`
- `/interview?category=Technical`
- `/evaluate`
- `/report/{id}`
- `/history`
- `/resume`
- `/api/health`

## Current limitations / future improvements

- Local answer scoring is heuristic and is not a validated assessment.
- Resume skill extraction is keyword-based and does not measure proficiency.
- Questions come from a fixed question bank; adaptive difficulty is not implemented.
- Voice input, speech-to-text, code execution sandbox, email verification, password reset, CSRF protection, rate limiting, and production HTTPS/cookie configuration are not implemented.
- Before public deployment, add CSRF protection, stricter upload validation, secure cookie settings behind HTTPS, rate limiting, data retention/deletion controls, and robust secret management.
- Do not upload real resumes, credentials, API keys, or a database containing personal information.

## Suggested demo screenshots

Add your own screenshots to a `screenshots/` folder and link them here before publishing:
- Landing / dashboard
- Interview question and answer form
- Evaluation report
- Resume skill extraction

## License

No license is specified yet. Add a license file if you want to explicitly allow others to reuse the code.
