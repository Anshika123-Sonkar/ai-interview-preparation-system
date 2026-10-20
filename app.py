import os, re, json, sqlite3, hashlib, secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "resumes"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

app = FastAPI(title="AI Interview Preparation & Evaluation System")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-only-change-this-secret"),
    same_site="lax",
    https_only=os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true",
)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))

QUESTION_BANK = {
    "Technical": [
        ("Explain the difference between supervised and unsupervised learning.", "machine learning, labeled data, classification, regression, clustering", "beginner"),
        ("What is overfitting, and how can you reduce it?", "training data, generalization, regularization, cross validation, dropout", "intermediate"),
        ("Explain precision, recall, and F1-score.", "true positive, false positive, false negative, precision, recall, harmonic mean", "intermediate"),
        ("How does a Random Forest classifier work?", "decision trees, ensemble, bootstrap, random features, voting", "intermediate"),
        ("What is the difference between SQL WHERE and HAVING?", "where, rows, before grouping, having, groups, aggregate", "beginner"),
        ("Explain time complexity and compare linear search with binary search.", "time complexity, big o, linear, binary, sorted, log n", "intermediate"),
        ("What is data leakage in machine learning?", "target leakage, training, test data, features, evaluation, leakage", "advanced"),
        ("How would you handle an imbalanced fraud-detection dataset?", "class imbalance, precision, recall, f1, resampling, class weights, threshold", "advanced"),
    ],
    "HR": [
        ("Tell me about yourself and your career goals.", "education, skills, project, strengths, goal, role", "beginner"),
        ("Describe a challenge you faced and how you solved it.", "situation, task, action, result, learning, specific example", "intermediate"),
        ("Why should we select you for this internship?", "skills, evidence, projects, learning, contribution, motivation", "beginner"),
        ("What is one skill you are currently improving?", "honest, specific, plan, practice, progress, example", "beginner"),
    ],
    "Behavioral": [
        ("Tell me about a time you worked with a team.", "situation, task, action, result, communication, teamwork", "intermediate"),
        ("How do you manage multiple deadlines?", "prioritize, plan, deadline, break down, communicate, review", "beginner"),
        ("Describe a mistake and what you learned from it.", "mistake, responsibility, action, result, learning, prevention", "intermediate"),
    ],
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            category TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL,
            score REAL NOT NULL, feedback TEXT NOT NULL, strengths TEXT NOT NULL,
            improvements TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            filename TEXT NOT NULL, extracted_text TEXT NOT NULL,
            skills TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id))""")
init_db()

def hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${hashed}"

def verify_password(password: str, stored: str):
    try:
        salt, expected = stored.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt).split("$", 1)[1], expected)
    except Exception:
        return False

def current_user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    with db() as c:
        return c.execute("SELECT id, name, email FROM users WHERE id=?", (uid,)).fetchone()

def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user

def get_question(category: str, index: int):
    choices = QUESTION_BANK.get(category, QUESTION_BANK["Technical"])
    return choices[index % len(choices)]

def extract_skills(text: str):
    known = ["Python", "SQL", "Machine Learning", "Deep Learning", "Pandas", "NumPy",
             "Scikit-learn", "TensorFlow", "PyTorch", "NLP", "HTML", "CSS", "JavaScript",
             "React", "FastAPI", "Flask", "Power BI", "MySQL", "PostgreSQL", "Git",
             "Data Analysis", "Computer Vision", "Generative AI", "Prompt Engineering"]
    low = text.lower()
    found = [s for s in known if s.lower() in low]
    return found or ["No recognized skills found — add a skills section to your resume."]

def local_evaluate(question: str, answer: str, category: str):
    clean = re.sub(r"\s+", " ", answer).strip()
    if not clean:
        return {"score": 0, "feedback": "No answer was submitted. Try answering in your own words, with one example.",
                "strengths": [], "improvements": ["Submit an answer", "Explain the main concept", "Give a relevant example"]}
    words = re.findall(r"\b[\w'-]+\b", clean)
    q_terms = set(re.findall(r"[a-zA-Z]{4,}", question.lower()))
    a_terms = set(re.findall(r"[a-zA-Z]{4,}", clean.lower()))
    overlap = len(q_terms & a_terms) / max(1, len(q_terms))
    length_score = min(len(words) / 80, 1.0)
    structure = 1 if any(x in clean.lower() for x in ["because", "for example", "therefore", "first", "finally", "such as"]) else 0.4
    score = round(min(100, max(15, 30 + overlap * 35 + length_score * 20 + structure * 15)))
    strengths = []
    improvements = []
    if len(words) >= 35: strengths.append("You provided a reasonably developed response.")
    else: improvements.append("Add more detail; aim for a clear 4–7 sentence answer.")
    if structure > 0.4: strengths.append("Your answer uses a connecting phrase or example.")
    else: improvements.append("Structure the answer: definition → explanation → example → conclusion.")
    if overlap > 0.15: strengths.append("Some wording is relevant to the question.")
    else: improvements.append("Address the exact question before adding background information.")
    if category == "HR":
        improvements.append("For experience-based questions, use the STAR method: Situation, Task, Action, Result.")
    else:
        improvements.append("Include accurate technical terms and a concrete example where appropriate.")
    feedback = ("Local evaluation mode is a heuristic estimate, not a validated measure of interview ability. "
                "Review the suggestions and verify technical accuracy with trusted references.")
    return {"score": score, "feedback": feedback, "strengths": strengths, "improvements": improvements}

def ai_evaluate(question: str, answer: str, category: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return local_evaluate(question, answer, category)
    try:
        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        prompt = f"""Evaluate this practice interview answer for learning, not hiring.
Category: {category}
Question: {question}
Candidate answer: {answer}
Return only JSON with keys: score (integer 0-100), feedback (short paragraph),
strengths (array of 1-3 strings), improvements (array of 2-4 strings).
Score technical correctness/relevance/completeness/clarity. Do not infer personality,
confidence, protected traits, or employability. If answer is too short, say so.
Be constructive and do not claim certainty where the answer is ambiguous."""
        resp = client.chat.completions.create(
            model=model, temperature=0.2,
            messages=[{"role":"system","content":"You are a fair interview practice coach. Follow the requested JSON schema."},
                      {"role":"user","content":prompt}],
            response_format={"type":"json_object"}
        )
        data = json.loads(resp.choices[0].message.content)
        data["score"] = max(0, min(100, int(data.get("score", 0))))
        data["strengths"] = data.get("strengths", [])[:3]
        data["improvements"] = data.get("improvements", [])[:4]
        return data
    except Exception:
        result = local_evaluate(question, answer, category)
        result["feedback"] += " AI service was unavailable, so local evaluation was used."
        return result

def render(request: Request, name: str, context=None, status_code=200):
    data = {"request": request, "user": current_user(request)}
    if context:
        data.update(context)
    return templates.TemplateResponse(request=request, name=name, context=data, status_code=status_code)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if current_user(request):
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "index.html")

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return render(request, "signup.html")

@app.post("/signup")
def signup(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    name, email = name.strip(), email.strip().lower()
    if len(name) < 2 or len(password) < 8:
        return render(request, "signup.html", {"error":"Enter your name and a password of at least 8 characters."}, 400)
    try:
        with db() as c:
            cur = c.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                            (name, email, hash_password(password), datetime.now().isoformat(timespec="seconds")))
            uid = cur.lastrowid
        request.session["user_id"] = uid
        return RedirectResponse("/dashboard", status_code=303)
    except sqlite3.IntegrityError:
        return render(request, "signup.html", {"error":"An account with this email already exists."}, 400)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html")

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    with db() as c:
        user = c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        return render(request, "login.html", {"error":"Invalid email or password."}, 400)
    request.session.clear()
    request.session["user_id"] = user["id"]
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = require_user(request)
    with db() as c:
        rows = c.execute("SELECT * FROM interviews WHERE user_id=? ORDER BY id DESC LIMIT 5", (user["id"],)).fetchall()
        stats = c.execute("SELECT COUNT(*) n, AVG(score) avg FROM interviews WHERE user_id=?", (user["id"],)).fetchone()
        resume = c.execute("SELECT * FROM resumes WHERE user_id=? ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
    return render(request, "dashboard.html", {"history": rows, "count": stats["n"],
                  "average": round(stats["avg"] or 0), "resume": resume})

@app.get("/interview", response_class=HTMLResponse)
def interview_page(request: Request, category: str = "Technical", index: int = 0):
    require_user(request)
    if category not in QUESTION_BANK:
        category = "Technical"
    question, rubric, difficulty = get_question(category, max(0, index))
    return render(request, "interview.html", {"category":category, "question":question,
                  "index":max(0,index), "difficulty":difficulty, "categories":list(QUESTION_BANK.keys())})

@app.post("/evaluate")
def evaluate(request: Request, category: str = Form(...), question: str = Form(...), answer: str = Form(...)):
    user = require_user(request)
    if category not in QUESTION_BANK:
        category = "Technical"
    allowed_questions = {item[0] for item in QUESTION_BANK[category]}
    if question not in allowed_questions:
        question = QUESTION_BANK[category][0][0]
    answer = answer.strip()
    if len(answer) > 12000:
        return render(request, "interview.html", {"category":category, "question":question,
            "index":0, "difficulty":"practice", "categories":list(QUESTION_BANK.keys()),
            "error":"Answer is too long. Please keep it under 12,000 characters."}, 400)
    result = ai_evaluate(question, answer, category)
    now = datetime.now().isoformat(timespec="seconds")
    with db() as c:
        cur = c.execute("""INSERT INTO interviews
          (user_id,category,question,answer,score,feedback,strengths,improvements,created_at)
          VALUES(?,?,?,?,?,?,?,?,?)""",
          (user["id"], category, question, answer, result["score"], result["feedback"],
           json.dumps(result["strengths"]), json.dumps(result["improvements"]), now))
        iid = cur.lastrowid
    return RedirectResponse(f"/report/{iid}", status_code=303)

@app.get("/report/{interview_id}", response_class=HTMLResponse)
def report(request: Request, interview_id: int):
    user = require_user(request)
    with db() as c:
        row = c.execute("SELECT * FROM interviews WHERE id=? AND user_id=?", (interview_id,user["id"])).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    data = dict(row)
    data["strengths"] = json.loads(data["strengths"])
    data["improvements"] = json.loads(data["improvements"])
    return render(request, "report.html", {"report":data})

@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    user = require_user(request)
    with db() as c:
        rows = c.execute("SELECT * FROM interviews WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    return render(request, "history.html", {"history":rows})

@app.get("/resume", response_class=HTMLResponse)
def resume_page(request: Request):
    require_user(request)
    return render(request, "resume.html")

@app.post("/resume")
async def upload_resume(request: Request, resume: UploadFile = File(...)):
    user = require_user(request)
    filename = Path(resume.filename or "resume").name
    ext = Path(filename).suffix.lower()
    if ext not in {".pdf", ".txt"}:
        return render(request, "resume.html", {"error":"Please upload a PDF or TXT file."}, 400)
    raw = await resume.read()
    if len(raw) > 5 * 1024 * 1024:
        return render(request, "resume.html", {"error":"File must be smaller than 5 MB."}, 400)
    extracted = ""
    try:
        if ext == ".txt":
            extracted = raw.decode("utf-8", errors="ignore")
        elif PdfReader:
            import io
            reader = PdfReader(io.BytesIO(raw))
            extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        extracted = ""
    if not extracted.strip():
        return render(request, "resume.html", {"error":"Could not extract text. Try a text-based PDF or TXT file."}, 400)
    skills = extract_skills(extracted)
    with db() as c:
        c.execute("INSERT INTO resumes(user_id,filename,extracted_text,skills,created_at) VALUES(?,?,?,?,?)",
                  (user["id"], filename, extracted[:50000], json.dumps(skills),
                   datetime.now().isoformat(timespec="seconds")))
    return render(request, "resume.html", {"filename":filename, "skills":skills, "success":"Resume analyzed successfully."})

@app.get("/api/health")
def health():
    return {"status":"ok", "app":"AI Interview Preparation & Evaluation System",
            "ai_mode":"openai" if os.getenv("OPENAI_API_KEY") and OpenAI else "local"}
