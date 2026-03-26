QUESTIONS = [
"I feel calm and emotionally balanced",
"I feel satisfied with my life",
"I feel hopeful about my future",
"I am able to manage stress effectively",
"I feel connected to people around me",
"I feel motivated to carry out daily tasks",
"I enjoy activities I usually like",
"I feel confident in myself",
"I feel mentally stable and in control",
"I feel a sense of purpose in life",

"I feel nervous, anxious, or on edge",
"I find it difficult to control my worries",
"I overthink situations excessively",
"I feel restless or unable to relax",
"I experience sudden feelings of panic",
"I worry about things beyond my control",
"I feel tense or easily startled",
"I struggle to concentrate due to worry",
"I feel a sense of impending danger",
"I have trouble sleeping due to overthinking",

"I feel down, depressed, or hopeless",
"I have little interest or pleasure in activities",
"I feel tired or lack energy",
"I struggle with motivation",
"I feel worthless or excessively guilty",
"I find it difficult to concentrate",
"I feel emotionally numb",
"I withdraw from social interactions",
"I feel like things won’t improve",
"I struggle to manage daily routines"
]
import os
from flask import Flask, render_template, request, send_file, session
import pickle
import re
import tempfile
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)
app = Flask(__name__)
app.secret_key = "mental_health_secure_key"

# ---------- SAFE MODEL LOAD ----------
try:
    model = pickle.load(open("model.pkl", "rb"))
    vectorizer = pickle.load(open("vectorizer.pkl", "rb"))
except Exception as e:
    print("Model load failed:", e)
    model = None
    vectorizer = None


# ---------- PREPROCESS ----------
def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    return text


# ---------- ROUTES ----------
@app.route("/")
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
    return render_template("checklist.html", text="", category="general")


@app.route("/checklist_text", methods=["POST"])
def checklist_text():
    text = request.form.get("user_input", "")
    return render_template("checklist.html", text=text, category="general")


# ---------- PREDICT ----------
@app.route("/predict", methods=["POST"])
def predict():

    text = request.form.get("text", "")

    # ---------- ML ----------
    ml_dep = ml_anx = ml_norm = 0

    if model and vectorizer and text.strip():
        processed = preprocess(text)
        vector = vectorizer.transform([processed])
        probs = model.predict_proba(vector)[0]
        labels = model.classes_
        scores = dict(zip(labels, probs))

        ml_dep = scores.get("depression", 0) * 100
        ml_anx = scores.get("anxiety", 0) * 100
        ml_norm = scores.get("normal", 0) * 100


    # ---------- CHECKLIST ----------
    dep_score = 0
    anx_score = 0
    pos_score = 0
    responses = {}

    options = ["Not at all", "Rarely", "Sometimes", "Often", "Almost always"]

    for i in range(1, 31):
        raw_val = request.form.get(f"q{i}")
        if raw_val is None:
            continue  # skip unanswered question
        val = int(request.form.get(f"q{i}", 0))
        responses[f"Question {i}"] = options[val]

        if 1 <= i <= 10:
            pos_score += val
        elif 11 <= i <= 20:
            anx_score += val
        elif 21 <= i <= 30:
            dep_score += val


    # ---------- NORMALIZATION ----------
    max_section = 10 * 4

    c_dep = (dep_score / max_section) * 100
    c_anx = (anx_score / max_section) * 100
    c_norm = (pos_score / max_section) * 100


    # ---------- COMBINE ----------
    f_dep = (0.6 * ml_dep) + (0.4 * c_dep)
    f_anx = (0.6 * ml_anx) + (0.4 * c_anx)
    f_norm = (0.6 * ml_norm) + (0.4 * c_norm)

    total = f_dep + f_anx + f_norm or 1

    depression = round((f_dep / total) * 100, 2)
    anxiety = round((f_anx / total) * 100, 2)
    normal = round((f_norm / total) * 100, 2)


    # ---------- FINAL DECISION ----------
    if f_dep == 0 and f_anx == 0 and f_norm == 0:
        final = "Confused and Uncertain"
    else:
        scores = {
            "Depression": f_dep,
            "Anxiety": f_anx,
            "Normal": f_norm
        }

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top1, top2 = sorted_scores[0], sorted_scores[1]

        if abs(top1[1] - top2[1]) < 8:
            combo = sorted([top1[0], top2[0]])
            final = f"{combo[0]} & {combo[1]}"
        else:
            final = top1[0]


    # ---------- LABEL SET ----------
    if final == "Confused and Uncertain":
        labels = {"Confused"}
    else:
        labels = set(final.split(" & "))


    # ---------- MESSAGE ----------
    if labels == {"Depression"}:
        message = "Your responses suggest signs of DEPRESSION. It may help to talk to someone you trust or seek professional support."

    elif labels == {"Anxiety"}:
        message = "Your responses indicate elevated ANXIETY levels. Practicing relaxation techniques and reaching out for support could help."

    elif labels == {"Normal"}:
        message = "Your responses suggest a generally balanced emotional state. Continue maintaining your well-being."

    elif labels == {"Depression", "Anxiety"}:
        message = "Your responses indicate both ANXIETY and DEPRESSION symptoms. It is important to seek support and not handle this alone."

    elif labels == {"Depression", "Normal"}:
        message = "MILD DEPRESSION detected. Early attention can help improve your well-being."

    elif labels == {"Anxiety", "Normal"}:
        message = "MILD ANXIETY detected. You are managing well, but small steps can help reduce stress."

    elif labels == {"Confused"}:
        message = "Your responses do not clearly indicate a specific pattern. Consider reflecting more or seeking professional guidance."

    else:
        message = "Your responses show mixed emotional patterns. Paying attention to your mental health is important."


    # ---------- RISK ----------
    severity = max(f_dep, f_anx)

    if "Depression" in final and "Anxiety" in final:
        severity += 10

    if severity >= 65:
        risk = "High Risk"
    elif severity >= 35:
        risk = "Moderate Risk"
    else:
        risk = "Low Risk"


    # ---------- SUPPORT ----------
    support_db = {
        "Depression": [
            {
                "name": "AASRA",
                "link": "https://www.aasra.info",
                "desc": "24/7 emotional support helpline for individuals experiencing distress or depression."
            }
        ],

        "Anxiety": [
            {
                "name": "MindPeers",
                "link": "https://mindpeers.co",
                "desc": "Professional therapy and tools to manage anxiety and stress effectively."
            }
        ],

        "Normal": [
            {
                "name": "Oppam",
                "link": "https://oppam.me",
                "desc": "A platform to maintain emotional well-being and stay mentally balanced."
            }
        ],

        "Depression & Anxiety": [
            {
                "name": "AASRA",
                "link": "https://www.aasra.info",
                "desc": "24/7 support for emotional distress, depression and crisis situations."
            },
            {
                "name": "MindPeers",
                "link": "https://mindpeers.co",
                "desc": "Guided therapy and mental health tools for anxiety and depression."
            }
        ],

        "Depression & Normal": [
            {
                "name": "iCALL",
                "link": "https://icallhelpline.org",
                "desc": "Professional counselling service for early signs of emotional distress."
            }
        ],

        "Anxiety & Normal": [
            {
                "name": "BetterLYF",
                "link": "https://betterlyf.com",
                "desc": "Online counselling and stress management support."
            }
        ],

        "Confused and Uncertain": [
            {
                "name": "iCALL",
                "link": "https://icallhelpline.org",
                "desc": "Talk to professionals to better understand your emotional state."
            },
            {
                "name": "AASRA",
                "link": "https://www.aasra.info",
                "desc": "Immediate emotional support when you're unsure about your feelings."
            }
        ]
    }

    support = support_db.get(final, [])


    # ---------- SUPPORT TITLE ----------
    if "Depression" in final and "Anxiety" in final:
        support_title = "Support for anxiety & depression"
    elif "Depression" in final:
        support_title = "Support for depression"
    elif "Anxiety" in final:
        support_title = "Support for anxiety"
    elif final == "Normal":
        support_title = "Resources to maintain well-being"
    elif final == "Confused and Uncertain":
        support_title = "General mental health support"
    else:
        support_title = "Support resources"


    # ---------- STORE ----------
    session['latest_result'] = {
        "text": text,
        "final": final,
        "depression": depression,
        "anxiety": anxiety,
        "normal": normal,
        "risk": risk,
        "responses": responses
    }


    # ---------- UI WIDTH ----------
    dep_ui = depression if depression > 2 else 2
    anx_ui = anxiety if anxiety > 2 else 2
    norm_ui = normal if normal > 2 else 2


    return render_template(
        "result.html",
        depression=depression,
        anxiety=anxiety,
        normal=normal,
        dep_ui=dep_ui,
        anx_ui=anx_ui,
        norm_ui=norm_ui,
        final=final,
        risk=risk,
        support=support,
        support_title=support_title,
        message=message
    )


# ---------- DOWNLOAD ----------
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import os


@app.route("/download")
def download():

    res = session.get('latest_result')
    user = session.get('user_info', {})

    if not res:
        return "No report available"

    REPORT_FOLDER = "reports"
    os.makedirs(REPORT_FOLDER, exist_ok=True)

    name = user.get('name', 'report').replace(" ", "_")
    file_path = os.path.join(REPORT_FOLDER, f"{name}.pdf")

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []

    # ---------- TITLE ----------
    content.append(Paragraph("<b>MindWatch Mental Health Report</b>", styles["Title"]))
    content.append(Spacer(1, 20))

    # ---------- USER DETAILS TABLE ----------
    user_data = [
        ["Name", user.get('name')],
        ["Age", user.get('age')],
        ["Place", user.get('place')],
        ["Email", user.get('email')],
    ]

    table = Table(user_data, colWidths=[120, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.beige),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))

    content.append(Paragraph("<b>User Details</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))
    content.append(table)
    content.append(Spacer(1, 20))

    # ---------- RESULT ----------
    content.append(Paragraph("<b>Assessment Result</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    content.append(Paragraph(f"<b>Final State:</b> {res['final']}", styles["Normal"]))
    content.append(Paragraph(f"<b>Risk Level:</b> {res['risk']}", styles["Normal"]))
    content.append(Spacer(1, 10))

    # ---------- SCORES TABLE ----------
    score_data = [
        ["Metric", "Percentage"],
        ["Depression", f"{res['depression']}%"],
        ["Anxiety", f"{res['anxiety']}%"],
        ["Normal", f"{res['normal']}%"]
    ]

    score_table = Table(score_data, colWidths=[200, 200])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black)
    ]))

    content.append(score_table)
    content.append(Spacer(1, 20))

    # ---------- RESPONSES TABLE (SORTED) ----------
    content.append(Paragraph("<b>Responses</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    # SORT QUESTIONS PROPERLY
    sorted_responses = sorted(res['responses'].items(), key=lambda x: int(x[0].split()[1]))

    response_data = [["Question", "Answer"]]

    # ---------- RESPONSES TABLE WITH QUESTIONS ----------
    content.append(Paragraph("<b>Responses</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    sorted_responses = sorted(
        res['responses'].items(),
        key=lambda x: int(x[0].split()[1])
    )

    response_data = [["Question", "Your Answer"]]

    for q, ans in sorted_responses:
        q_num = int(q.split()[1])
        question_text = QUESTIONS[q_num - 1]

        full_question = f"Q{q_num}. {question_text}"
        response_data.append([full_question, ans])

    response_table = Table(response_data, colWidths=[320, 130])
    response_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.3, colors.grey)
    ]))

    content.append(response_table)
    content.append(Spacer(1, 20))


    # ---------- DISCLAIMER ----------
    content.append(Paragraph(
        "<i>Disclaimer: This report is for awareness purposes only and not a medical diagnosis. "
        "Please consult a mental health professional.</i>",
        styles["Normal"]
    ))

    doc.build(content)

    return send_file(file_path, as_attachment=True)


# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)