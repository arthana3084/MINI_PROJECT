import json
import os
import pickle
import re
import uuid
from datetime import datetime, timezone

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

app = Flask(__name__)
app.secret_key = "mental_health_secure_key"


@app.context_processor
def inject_user():
    return {"current_user": session.get("username")}

REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

DATA_DIR = "data"
USER_STORE = os.path.join(DATA_DIR, "users.json")
os.makedirs(DATA_DIR, exist_ok=True)


def _load_user_store():
    if not os.path.isfile(USER_STORE):
        return {"users": {}}
    try:
        with open(USER_STORE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"users": {}}


def _save_user_store(store):
    with open(USER_STORE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


def _append_user_report(username, result_dict):
    """Persist a completed assessment for a signed-in user (server-side history)."""
    store = _load_user_store()
    users = store.setdefault("users", {})
    user = users.get(username)
    if not user:
        return None
    rec = dict(result_dict)
    rec["id"] = str(uuid.uuid4())
    rec["ts"] = datetime.now(timezone.utc).isoformat()
    user.setdefault("reports", []).append(rec)
    _save_user_store(store)
    return rec["id"]


def _get_user_report(username, report_id):
    store = _load_user_store()
    user = store.get("users", {}).get(username)
    if not user:
        return None
    for r in user.get("reports", []):
        if r.get("id") == report_id:
            return r
    return None


def _report_for_session(stored):
    """Strip server metadata for PDF / display via session."""
    out = {k: v for k, v in stored.items() if k not in ("id", "ts")}
    return out

# ---------- LOAD ML MODEL ----------
try:
    model = pickle.load(open("model.pkl", "rb"))
    vectorizer = pickle.load(open("vectorizer.pkl", "rb"))
    ML_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] ML model not loaded: {e}")
    ML_AVAILABLE = False

# ---------- QUESTION BANKS ----------
ANXIETY_QUESTIONS = [
    "I feel nervous, anxious, or on edge",
    "I find it difficult to control my worries",
    "I tend to overthink situations excessively",
    "I feel restless or unable to relax",
    "I experience sudden feelings of panic",
    "I worry about things beyond my control",
    "I feel tense or easily startled",
    "I struggle to concentrate due to worry",
    "I feel a sense of impending danger",
    "I have trouble sleeping due to overthinking"
]

DEPRESSION_QUESTIONS = [
    "I feel down, depressed, or hopeless",
    "I have little interest or pleasure in activities",
    "I feel tired or lack energy",
    "I struggle with motivation",
    "I feel worthless or excessively guilty",
    "I find it difficult to concentrate",
    "I feel emotionally numb",
    "I withdraw from social interactions",
    "I feel like things won't improve",
    "I struggle to manage daily routines"
]

GENERAL_POSITIVE_QUESTIONS = [
    "I feel calm and emotionally balanced",
    "I feel satisfied with my life",
    "I feel hopeful about my future",
    "I am able to manage stress effectively",
    "I feel connected to people around me",
    "I feel motivated to carry out daily tasks",
    "I enjoy activities I usually like",
    "I feel confident in myself",
    "I feel mentally stable and in control",
    "I feel a sense of purpose in life"
]

GENERAL_QUESTIONS = GENERAL_POSITIVE_QUESTIONS + ANXIETY_QUESTIONS + DEPRESSION_QUESTIONS

# ---------- CLASSIFICATION ----------
def classify_depression(score, num_questions=10):
    """Scale-aware classification based on number of questions answered."""
    max_possible = num_questions * 4
    pct = (score / max_possible) * 100 if max_possible > 0 else 0
    if pct <= 15:
        return "Minimal"
    elif pct <= 35:
        return "Mild"
    elif pct <= 55:
        return "Moderate"
    elif pct <= 75:
        return "Moderately Severe"
    else:
        return "Severe"

def classify_anxiety(score, num_questions=10):
    """Scale-aware classification based on number of questions answered."""
    max_possible = num_questions * 4
    pct = (score / max_possible) * 100 if max_possible > 0 else 0
    if pct <= 15:
        return "Minimal"
    elif pct <= 35:
        return "Mild"
    elif pct <= 60:
        return "Moderate"
    else:
        return "Severe"

def overall_assessment(dep, anx):
    severity = {"Minimal": 0, "Mild": 1, "Moderate": 2, "Moderately Severe": 3, "Severe": 4}
    dep_n = severity.get(dep, 0)
    anx_n = severity.get(anx, 0)
    worst = max(dep_n, anx_n)
    if worst >= 3:
        return "High Risk"
    elif worst == 2:
        return "Moderate Risk"
    elif worst == 1:
        return "Mild Concern"
    else:
        return "Minimal / No Significant Concern"

def score_to_bar_percent(score, num_questions):
    """Linear 0-100 bar width: raw sum as percent of maximum (num_questions × 4)."""
    max_possible = num_questions * 4
    if max_possible <= 0:
        return 0
    pct = (score / max_possible) * 100
    return int(round(min(100.0, max(0.0, pct))))

# ---------- ML PREDICTION ----------
def predict_category(text):
    """Use ML model to classify text. Returns 'anxiety', 'depression', or 'general'."""
    if not ML_AVAILABLE or not text or not text.strip():
        return "general"

    text_lower = text.lower()

    # Keyword-based fast checks first (for robustness)
    import re
    anxiety_keywords = [
        r"\banxious\b", r"\banxiety\b", r"\bpanic\b", r"\bworry\b", r"\bworried\b", r"\bnervous\b", r"\brestless\b",
        r"\bfear\b", r"\bscared\b", r"\btense\b", r"\boverthink\b", r"\boverwhelmed\b", r"\bdread\b", r"\bphobia\b",
        r"\bon edge\b", r"\bheart racing\b", r"can't calm", r"\bstressed\b"
    ]
    depression_keywords = [
        r"\bdepressed\b", r"\bdepression\b", r"\bsad\b", r"\bhopeless\b", r"\bworthless\b", r"\bempty\b",
        r"\bnumb\b", r"no motivation", r"\bunmotivated\b", r"tired all the time", r"no energy",
        r"nothing matters", r"give up", r"no point", r"\bcrying\b", r"\blonely\b", r"\bisolated\b",
        r"\bwithdraw\b", r"\bsuicidal\b", r"don't want to live", r"\bpointless\b", r"\blow\b", r"\bdown\b"
    ]

    anx_hits = sum(1 for kw in anxiety_keywords if re.search(kw, text_lower))
    dep_hits = sum(1 for kw in depression_keywords if re.search(kw, text_lower))
    
    # If clear keyword majority, use that
    if anx_hits > dep_hits and anx_hits >= 1:
        keyword_vote = "anxiety"
    elif dep_hits > anx_hits and dep_hits >= 1:
        keyword_vote = "depression"
    else:
        keyword_vote = None

    # ML model vote
    try:
        vec = vectorizer.transform([text])
        ml_raw = model.predict(vec)[0].lower().strip()
        print(f"--- ML Predicts: '{ml_raw}' for text '{text}' ---")
        # Normalise label variants
        if "anxiety" in ml_raw:
            ml_vote = "anxiety"
        elif "depress" in ml_raw:
            ml_vote = "depression"
        else:
            ml_vote = "general"
    except Exception as e:
        print(f"--- ML Error: {e} ---")
        ml_vote = "general"

    # Strategy: Trust the ML model first. Only apply keyword override if ML predicts "general"/"Normal"
    # but the user used highly specific words that the model missed (common in very short phrases).
    if ml_vote != "general":
        return ml_vote
    elif keyword_vote:
        print(f"--- ML predicted general, but keyword safety triggered: {keyword_vote} ---")
        return keyword_vote
    else:
        return "general"

# ---------- ROUTES ----------
@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route("/landing")
def home():
    return render_template("index.html")

@app.route("/text", methods=["POST"])
def text():
    name = request.form.get("name")
    age = request.form.get("age")
    email = request.form.get("email")
    place = request.form.get("place")

    # ✅ AGE VALIDATION
    try:
        age = int(age)
        if age <= 0 or age > 120:
            return "Invalid age. Please enter a valid age between 1 and 120."
    except:
        return "Invalid input for age."

    # store only if valid
    session['user_info'] = {
        "name": name,
        "age": age,
        "email": email,
        "place": place
    }

    return render_template("choice.html")


@app.route("/choice")
def choice():
    return render_template("choice.html")


@app.route("/text_input")
def text_input():
    return render_template("text.html")

@app.route("/checklist_general")
def checklist_general():
    # Direct general checklist (no text analysis)
    return render_template("checklist.html", category="general", text="", nav_show_category=True)

# ---------- ANALYZE TEXT → ROUTE TO CORRECT CHECKLIST ----------
@app.route("/analyze_text", methods=["POST"])
def analyze_text():
    user_text = request.form.get("user_text", "").strip()
    category = predict_category(user_text)
    # Store the input text and detected category in session
    session['user_text'] = user_text
    session['detected_category'] = category
    return render_template("checklist.html", category=category, text=user_text, nav_show_category=True)

# ---------- PREDICT (SCORE + CLASSIFY) ----------
@app.route("/predict", methods=["POST"])
def predict():
    category = request.form.get("category", "general")
    options = ["Not at all", "Rarely", "Sometimes", "Often", "Almost always"]

    dep_score = 0
    anx_score = 0
    pos_score = 0
    responses = {}

    # ---- Determine which questions were shown ----
    if category == "anxiety":
        num_q = len(ANXIETY_QUESTIONS)
        for i in range(1, num_q + 1):
            raw_val = request.form.get(f"q{i}")
            if raw_val is None:
                continue
            val = int(raw_val)
            responses[f"Q{i}"] = {"question": ANXIETY_QUESTIONS[i - 1], "answer": options[val]}
            anx_score += val
        anx_level = classify_anxiety(anx_score, num_q)
        dep_level = "N/A"

    elif category == "depression":
        num_q = len(DEPRESSION_QUESTIONS)
        for i in range(1, num_q + 1):
            raw_val = request.form.get(f"q{i}")
            if raw_val is None:
                continue
            val = int(raw_val)
            responses[f"Q{i}"] = {"question": DEPRESSION_QUESTIONS[i - 1], "answer": options[val]}
            dep_score += val
        dep_level = classify_depression(dep_score, num_q)
        anx_level = "N/A"

    else:  # general — 30 questions: 1-10 positive, 11-20 anxiety, 21-30 depression
        for i in range(1, 31):
            raw_val = request.form.get(f"q{i}")
            if raw_val is None:
                continue
            val = int(raw_val)
            if 1 <= i <= 10:
                q_text = GENERAL_POSITIVE_QUESTIONS[i - 1]
                responses[f"Q{i}"] = {"question": q_text, "answer": options[val]}
                pos_score += val  # higher = more positive (NOT reversed — see below)
            elif 11 <= i <= 20:
                q_text = ANXIETY_QUESTIONS[i - 11]
                responses[f"Q{i}"] = {"question": q_text, "answer": options[val]}
                anx_score += val
            elif 21 <= i <= 30:
                q_text = DEPRESSION_QUESTIONS[i - 21]
                responses[f"Q{i}"] = {"question": q_text, "answer": options[val]}
                dep_score += val
        dep_level = classify_depression(dep_score, 10)
        anx_level = classify_anxiety(anx_score, 10)

    # ---------- OVERALL RISK ----------
    # For single-category checklists, only use the relevant score
    if category == "anxiety":
        risk = overall_assessment("Minimal", anx_level)
    elif category == "depression":
        risk = overall_assessment(dep_level, "Minimal")
    else:
        risk = overall_assessment(dep_level, anx_level)

    # ---------- WELL-BEING & BAR WIDTHS (continuous % of scale, not label buckets) ----------
    n_dep = len(DEPRESSION_QUESTIONS)
    n_anx = len(ANXIETY_QUESTIONS)
    dep_ui = score_to_bar_percent(dep_score, n_dep) if dep_level != "N/A" else 0
    anx_ui = score_to_bar_percent(anx_score, n_anx) if anx_level != "N/A" else 0

    if category == "general":
        norm_ui = score_to_bar_percent(pos_score, len(GENERAL_POSITIVE_QUESTIONS))
    elif category == "anxiety":
        norm_ui = max(0, 100 - anx_ui)
    elif category == "depression":
        norm_ui = max(0, 100 - dep_ui)
    else:
        norm_ui = 50

    # ---------- MESSAGES ----------
    anx_display = anx_level if anx_level != "N/A" else "Not assessed"
    dep_display = dep_level if dep_level != "N/A" else "Not assessed"

    message = f"""
    <b>Assessment Summary</b><br><br>
    {"<b>Depression Level:</b> " + dep_display + "<br>" if dep_level != "N/A" else ""}
    {"<b>Anxiety Level:</b> " + anx_display + "<br>" if anx_level != "N/A" else ""}
    <b>Overall Risk:</b> {risk}<br><br>

    <b>Interpretation:</b><br>
    """

    if category == "anxiety":
        message += f"Your responses indicate <b>{anx_level.lower()}</b> anxiety symptoms.<br><br>"
    elif category == "depression":
        message += f"Your responses indicate <b>{dep_level.lower()}</b> depressive symptoms.<br><br>"
    else:
        message += f"Your responses indicate {dep_level.lower()} depressive symptoms and {anx_level.lower()} anxiety symptoms.<br><br>"

    message += "<b>Recommendation:</b><br>Monitor your mental health and seek support if needed.<br><br>"
    message += "<i>This is a screening tool and not a clinical diagnosis.</i>"

    # ---------- CONTRADICTION CHECK (only general) ----------
    if category == "general":
        if pos_score < 10 and (dep_score > 30 or anx_score > 30):
            risk = "Inconsistent Response Pattern"
            message = """
            <b>Notice:</b><br><br>
            Your responses show very high distress alongside inconsistently low positive scores.<br><br>
            This may suggest inconsistent answering or mixed emotional conditions.<br><br>
            Please consider retaking the assessment carefully.
            """

    # ---------- SUPPORT ----------
    anxiety_support = []
    depression_support = []
    general_support = []

    if anx_level not in ["Minimal", "N/A"]:
        anxiety_support = [
            {"name": "Kiran Helpline", "link": "tel:1800-599-0019", "desc": "24/7 mental health support helpline"},
            {"name": "Headspace", "link": "https://www.headspace.com", "desc": "Guided relaxation and mindfulness techniques"},
            {"name": "Wysa", "link": "https://www.wysa.com", "desc": "AI-powered emotional support chatbot"}
        ]

    if dep_level not in ["Minimal", "N/A"]:
        depression_support = [
            {"name": "AASRA", "link": "https://www.aasra.info", "desc": "Crisis support and suicide prevention"},
            {"name": "The Mind Clan", "link": "https://themindclan.com", "desc": "Connect with verified therapists"},
            {"name": "Wysa", "link": "https://www.wysa.com", "desc": "Emotional support and CBT exercises"}
        ]

    if not anxiety_support and not depression_support:
        general_support = [
            {"name": "Headspace", "link": "https://www.headspace.com", "desc": "Mindfulness and meditation"},
            {"name": "Wysa", "link": "https://www.wysa.com", "desc": "Mood check-in and support"}
        ]

    # ---------- SAVE TO SESSION (+ optional server-side copy for signed-in users) ----------
    snapshot = {
        "category": category,
        "dep_level": dep_level,
        "anx_level": anx_level,
        "risk": risk,
        "responses": responses,
        "dep_ui": dep_ui,
        "anx_ui": anx_ui,
        "norm_ui": norm_ui,
        "message_html": message,
        "anxiety_support": anxiety_support,
        "depression_support": depression_support,
        "general_support": general_support,
    }
    session["latest_result"] = snapshot

    uname = session.get("username")
    if uname:
        _append_user_report(uname, snapshot)

    result_payload = {
        "category": category,
        "dep_level": dep_level,
        "anx_level": anx_level,
        "risk": risk,
        "dep_ui": dep_ui,
        "anx_ui": anx_ui,
        "norm_ui": norm_ui,
    }

    return render_template(
        "result.html",
        category=category,
        dep_ui=dep_ui,
        anx_ui=anx_ui,
        norm_ui=norm_ui,
        dep_level=dep_level,
        anx_level=anx_level,
        risk=risk,
        message=message,
        anxiety_support=anxiety_support,
        depression_support=depression_support,
        general_support=general_support,
        result_payload=result_payload,
        from_saved=False,
        saved_label="",
    )


def _valid_username(username):
    return bool(username and re.match(r"^[a-zA-Z0-9_]{3,32}$", username))


@app.route("/register", methods=["GET", "POST"])
def register():
    err = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not _valid_username(username):
            err = "Username must be 3–32 characters (letters, numbers, underscore)."
        elif len(password) < 6:
            err = "Password must be at least 6 characters."
        else:
            store = _load_user_store()
            users = store.setdefault("users", {})
            if username in users:
                err = "That username is already taken."
            else:
                users[username] = {
                    "password_hash": generate_password_hash(password),
                    "reports": [],
                }
                _save_user_store(store)
                session["username"] = username
                return redirect(url_for("home"))
    return render_template("register.html", error=err)


@app.route("/signin", methods=["GET", "POST"])
def signin():
    err = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        next_url = (request.form.get("next") or request.args.get("next") or "").strip() or url_for("home")
        store = _load_user_store()
        user = store.get("users", {}).get(username)
        if user and check_password_hash(user.get("password_hash", ""), password):
            session["username"] = username
            if not (next_url.startswith("/") and not next_url.startswith("//")):
                next_url = url_for("home")
            return redirect(next_url)
        err = "Invalid username or password."
    return render_template("signin.html", error=err)


@app.route("/signout")
def signout():
    session.pop("username", None)
    return redirect(url_for("home"))


@app.route("/reports")
def reports_list():
    uname = session.get("username")
    if not uname:
        return redirect(url_for("signin", next=request.path))
    store = _load_user_store()
    user = store.get("users", {}).get(uname, {})
    rows = list(reversed(user.get("reports", [])))
    return render_template("reports.html", reports=rows)


@app.route("/reports/<report_id>")
def report_view(report_id):
    uname = session.get("username")
    if not uname:
        return redirect(url_for("signin", next=request.path))
    r = _get_user_report(uname, report_id)
    if not r:
        abort(404)
    session["latest_result"] = _report_for_session(r)
    return render_template(
        "result.html",
        category=r["category"],
        dep_ui=r["dep_ui"],
        anx_ui=r["anx_ui"],
        norm_ui=r["norm_ui"],
        dep_level=r["dep_level"],
        anx_level=r["anx_level"],
        risk=r["risk"],
        message=r.get("message_html", ""),
        anxiety_support=r.get("anxiety_support") or [],
        depression_support=r.get("depression_support") or [],
        general_support=r.get("general_support") or [],
        result_payload={
            "category": r["category"],
            "dep_level": r["dep_level"],
            "anx_level": r["anx_level"],
            "risk": r["risk"],
            "dep_ui": r["dep_ui"],
            "anx_ui": r["anx_ui"],
            "norm_ui": r["norm_ui"],
        },
        from_saved=True,
        saved_label=r.get("ts", ""),
    )


# ---------- PDF DOWNLOAD ----------
@app.route("/download")
def download():
    res = session.get('latest_result')
    user = session.get('user_info', {})

    if not res:
        return "No report available. Please complete an assessment first.", 400

    name = (user.get('name', 'report') or 'report').replace(" ", "_")
    file_path = os.path.join(REPORT_FOLDER, f"{name}_report.pdf")

    def draw_border(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.grey)
        canvas.setLineWidth(2)
        canvas.rect(20, 20, 550, 800)
        canvas.restoreState()

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    content = []

    # Header
    try:
        logo = Image("static/logo.png", width=0.8 * inch, height=0.8 * inch)
        content.append(logo)
    except Exception:
        pass

    content.append(Paragraph(
        "<font size=24 color='#1f4037'><b>Mental Health Assessment Report</b></font>",
        styles["Title"]
    ))
    content.append(Spacer(1, 10))
    content.append(Paragraph(
        "<font size=12 color='#4f5f59'><i>Generated by MindWatch</i></font>",
        styles["Normal"]
    ))
    content.append(Spacer(1, 20))

    # User details
    content.append(Paragraph("<b>Patient Information</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))
    user_data = [
        ["Name", user.get('name', '-')],
        ["Age", user.get('age', '-')],
        ["Email", user.get('email', '-')],
        ["Location", user.get('place', '-')]
    ]
    table = Table(user_data, colWidths=[120, 320])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    content.append(table)
    content.append(Spacer(1, 20))

    # Visual summary
    content.append(Paragraph("<b>Visual Summary</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    def make_bar(width, color):
        return Table([[""]], colWidths=[max(width, 5)], rowHeights=[10],
                     style=[('BACKGROUND', (0, 0), (-1, -1), color)])

    category = res.get('category', 'general')
    graph_data = []
    if res.get('dep_ui', 0) > 0:
        graph_data.append(["Depression", make_bar(res['dep_ui'] * 2, colors.red)])
    if res.get('anx_ui', 0) > 0:
        graph_data.append(["Anxiety", make_bar(res['anx_ui'] * 2, colors.orange)])
    graph_data.append(["Well-being", make_bar(res.get('norm_ui', 50) * 2, colors.green)])

    if graph_data:
        graph_table = Table(graph_data, colWidths=[120, 300])
        graph_table.setStyle([('GRID', (0, 0), (-1, -1), 0.3, colors.grey)])
        content.append(graph_table)
    content.append(Spacer(1, 20))

    # Summary
    content.append(Paragraph("<b>Assessment Summary</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    summary_data = [["Risk Level", res['risk']]]
    if res['dep_level'] != "N/A":
        summary_data.insert(0, ["Depression Level", res['dep_level']])
    if res['anx_level'] != "N/A":
        summary_data.insert(0 if res['dep_level'] == "N/A" else 1, ["Anxiety Level", res['anx_level']])

    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    content.append(summary_table)
    content.append(Spacer(1, 20))

    # Interpretation
    content.append(Paragraph("<b>Clinical Interpretation</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    interp_parts = []
    if res['dep_level'] != "N/A":
        interp_parts.append(f"<b>Depression Level:</b> {res['dep_level']}")
    if res['anx_level'] != "N/A":
        interp_parts.append(f"<b>Anxiety Level:</b> {res['anx_level']}")
    interp_parts.append(f"<b>Overall Risk:</b> {res['risk']}")
    content.append(Paragraph("<br/>".join(interp_parts), styles["Normal"]))
    content.append(Spacer(1, 20))

    # Detailed responses
    content.append(PageBreak())
    content.append(Paragraph("<b>Detailed Questionnaire Responses</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    for key in sorted(res['responses'], key=lambda x: int(x[1:])):
        val = res['responses'][key]
        if isinstance(val, dict):
            content.append(Paragraph(f"<b>{key}:</b> {val['question']}", styles["Normal"]))
            content.append(Paragraph(f"Response: {val['answer']}", styles["Normal"]))
        else:
            content.append(Paragraph(f"<b>{key}:</b> {val}", styles["Normal"]))
        content.append(Spacer(1, 6))

    content.append(Spacer(1, 20))
    content.append(Paragraph(
        "<i>⚠️This report is for screening purposes only and not a clinical diagnosis.</i>",
        styles["Normal"]
    ))

    doc.build(content, onFirstPage=draw_border, onLaterPages=draw_border)
    return send_file(file_path, as_attachment=True)

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)