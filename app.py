import os
import pickle
from flask import Flask, render_template, request, send_file, session
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

app = Flask(__name__)
app.secret_key = "mental_health_secure_key"

REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

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

def level_to_percent(level):
    mapping = {
        "Minimal": 15,
        "Mild": 35,
        "Moderate": 60,
        "Moderately Severe": 80,
        "Severe": 100
    }
    return mapping.get(level, 15)

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
    session['user_info'] = {
        "name": request.form.get("name"),
        "age": request.form.get("age"),
        "email": request.form.get("email"),
        "place": request.form.get("place")
    }
    return render_template("choice.html")

@app.route("/text_input")
def text_input():
    return render_template("text.html")

@app.route("/checklist_general")
def checklist_general():
    # Direct general checklist (no text analysis)
    return render_template("checklist.html", category="general", text="")

# ---------- ANALYZE TEXT → ROUTE TO CORRECT CHECKLIST ----------
@app.route("/analyze_text", methods=["POST"])
def analyze_text():
    user_text = request.form.get("user_text", "").strip()
    category = predict_category(user_text)
    # Store the input text and detected category in session
    session['user_text'] = user_text
    session['detected_category'] = category
    return render_template("checklist.html", category=category, text=user_text)

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

    # ---------- WELL-BEING (only meaningful for general) ----------
    if category == "general" and pos_score > 0:
        # pos_score: higher = more positive feelings (0-40 range for 10 questions × 4)
        wellbeing_percent = int((pos_score / 40) * 100)
        norm_ui = max(10, wellbeing_percent)
    elif category == "anxiety":
        # Invert anxiety score as proxy for well-being
        norm_ui = max(10, 100 - level_to_percent(anx_level))
    elif category == "depression":
        norm_ui = max(10, 100 - level_to_percent(dep_level))
    else:
        norm_ui = 50

    dep_ui = level_to_percent(dep_level) if dep_level != "N/A" else 0
    anx_ui = level_to_percent(anx_level) if anx_level != "N/A" else 0

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

    # ---------- SAVE TO SESSION ----------
    session['latest_result'] = {
        "category": category,
        "dep_level": dep_level,
        "anx_level": anx_level,
        "risk": risk,
        "responses": responses,
        "dep_ui": dep_ui,
        "anx_ui": anx_ui,
        "norm_ui": norm_ui
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
        general_support=general_support
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

    for key, val in res['responses'].items():
        if isinstance(val, dict):
            content.append(Paragraph(f"<b>{key}:</b> {val['question']}", styles["Normal"]))
            content.append(Paragraph(f"Response: {val['answer']}", styles["Normal"]))
        else:
            content.append(Paragraph(f"<b>{key}:</b> {val}", styles["Normal"]))
        content.append(Spacer(1, 6))

    content.append(Spacer(1, 20))
    content.append(Paragraph(
        "<i>This report is for screening purposes only and not a clinical diagnosis.</i>",
        styles["Normal"]
    ))

    doc.build(content, onFirstPage=draw_border, onLaterPages=draw_border)
    return send_file(file_path, as_attachment=True)

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)