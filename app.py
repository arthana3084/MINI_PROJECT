import os
from flask import Flask, render_template, request, send_file, session
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "mental_health_secure_key"

REPORT_FOLDER = "reports"
os.makedirs(REPORT_FOLDER, exist_ok=True)

# ---------- QUESTIONS ----------
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

# ---------- CLASSIFICATION ----------
def classify_depression(score):
    if score <= 4:
        return "Minimal"
    elif score <= 9:
        return "Mild"
    elif score <= 14:
        return "Moderate"
    elif score <= 19:
        return "Moderately Severe"
    else:
        return "Severe"

def classify_anxiety(score):
    if score <= 4:
        return "Minimal"
    elif score <= 9:
        return "Mild"
    elif score <= 14:
        return "Moderate"
    else:
        return "Severe"

def overall_assessment(dep, anx):
    if dep in ["Severe", "Moderately Severe"] or anx == "Severe":
        return "High Risk"
    elif dep == "Moderate" or anx == "Moderate":
        return "Moderate Risk"
    elif dep == "Mild" or anx == "Mild":
        return "Mild Concern"
    else:
        return "Minimal / No Significant Concern"

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
    return render_template("checklist.html")

# ---------- PREDICT ----------
@app.route("/predict", methods=["POST"])
def predict():

    dep_score = 0
    anx_score = 0
    pos_score = 0
    responses = {}

    options = ["Not at all", "Rarely", "Sometimes", "Often", "Almost always"]

    for i in range(1, 31):
        raw_val = request.form.get(f"q{i}")
        if raw_val is None:
            continue

        val = int(raw_val)
        responses[f"Question {i}"] = options[val]

        if 1 <= i <= 10:
            pos_score += (4 - val)   # reverse scoring
        elif 11 <= i <= 20:
            anx_score += val
        elif 21 <= i <= 30:
            dep_score += val

    # ---------- CLASSIFICATION ----------
    dep_level = classify_depression(dep_score)
    anx_level = classify_anxiety(anx_score)

    # ---------- POSITIVE ADJUSTMENT ----------
    if pos_score > 25:
        if dep_level == "Moderate":
            dep_level = "Mild"
        elif dep_level == "Mild":
            dep_level = "Minimal"

        if anx_level == "Moderate":
            anx_level = "Mild"
        elif anx_level == "Mild":
            anx_level = "Minimal"

    risk = overall_assessment(dep_level, anx_level)

    # ---------- MESSAGE ----------
    message = f"""
    <b>Assessment Summary</b><br><br>

    <b>Depression Level:</b> {dep_level}<br>
    <b>Anxiety Level:</b> {anx_level}<br>
    <b>Overall Risk:</b> {risk}<br><br>

    <b>Interpretation:</b><br>
    Your responses indicate {dep_level.lower()} depressive symptoms and {anx_level.lower()} anxiety symptoms.<br><br>

    <b>Recommendation:</b><br>
    Monitor your mental health and seek support if needed.<br><br>

    <i>This is a screening tool and not a clinical diagnosis.</i>
    """

    # ---------- CONTRADICTION CHECK ----------
    if pos_score < 10 and (dep_score > 30 or anx_score > 30):
        risk = "Inconsistent Response Pattern"
        message = """
        <b>Notice:</b><br><br>
        Your responses indicate both high positive and high negative emotional states.<br><br>
        This may suggest inconsistent answering or mixed emotional conditions.<br><br>
        Please consider retaking the assessment carefully.
        """

    # ---------- LOW EMOTIONAL RESPONSE ----------
    elif pos_score >=30 and dep_score <=10 and anx_score <= 10:
        risk = "Disengagement or emotional numbness"
        message = """
        <b>Observation:</b><br><br>
        Your responses indicate very low emotional expression across both positive and negative experiences.<br><br>
        This may reflect emotional numbness or disengagement.<br><br>
        Consider monitoring your emotional well-being.
        """


    # ---------- GRAPH VALUES ----------
    def level_to_percent(level):
        mapping = {
            "Minimal": 20,
            "Mild": 40,
            "Moderate": 60,
            "Moderately Severe": 80,
            "Severe": 100
        }
        return mapping.get(level, 20)

    dep_ui = level_to_percent(dep_level)
    anx_ui = level_to_percent(anx_level)

    # ✅ CORRECT WELL-BEING (FIXED LOGIC)
    wellbeing_percent = max(0, 100 - int((pos_score / 40) * 100))
    norm_ui = max(10, wellbeing_percent)

    

    # ---------- SUPPORT ----------
    anxiety_support = []
    depression_support = []
    general_support = []

    if anx_level in ["Mild", "Moderate", "Severe"]:
        anxiety_support = [
            {"name": "Kiran Helpline", "link": "tel:1800-599-0019", "desc": "This is a 24/7 support for anxiety"},
            {"name": "Headspace", "link": "https://www.headspace.com", "desc": "Approach here to get some relaxation techniques"},
            {"name": "Wysa", "link": "https://www.wysa.com", "desc": "This is a support chatbot"}
        ]

    if dep_level in ["Mild", "Moderate", "Severe", "Moderately Severe"]:
        depression_support = [
            {"name": "AASRA", "link": "https://www.aasra.info", "desc": "Crisis support System"},
            {"name": "The Mind Clan", "link": "https://themindclan.com", "desc": "Find therapists here"},
            {"name": "Wysa", "link": "https://www.wysa.com", "desc": "Emotional support"}
        ]

    if not anxiety_support and not depression_support:
        general_support = [
            {"name": "Headspace", "link": "https://www.headspace.com", "desc": "Mindfulness"},
            {"name": "Wysa", "link": "https://www.wysa.com", "desc": "Check-in support"}
        ]
    session['latest_result'] = {
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

# ---------- PDF ----------
from reportlab.platypus import Image
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak

@app.route("/download")
def download():

    res = session.get('latest_result')
    user = session.get('user_info', {})

    if not res:
        return "No report available"

    name = user.get('name', 'report').replace(" ", "_")
    file_path = os.path.join(REPORT_FOLDER, f"{name}_report.pdf")

    # ---------- PAGE BORDER ----------
    def draw_border(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.grey)
        canvas.setLineWidth(2)
        canvas.rect(20, 20, 550, 800)
        canvas.restoreState()

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    content = []

    # ---------- HEADER ----------
    try:
        logo = Image("static/logo.png", width=0.8*inch, height=0.8*inch)
        content.append(logo)
    except:
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

    # ---------- USER DETAILS ----------
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
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))

    content.append(table)
    content.append(Spacer(1, 20))

    # ---------- GRAPH ----------
    content.append(Paragraph("<b>Visual Summary</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    def make_bar(width, color):
        return Table([[""]], colWidths=[width], rowHeights=[10],
                    style=[('BACKGROUND', (0,0), (-1,-1), color)])

    # Convert UI % to width
    dep_width = res.get('dep_ui', 40) * 2
    anx_width = res.get('anx_ui', 40) * 2
    norm_width = res.get('norm_ui', 40) * 2   # ✅ CORRECT

    graph_data = [
        ["Depression", make_bar(dep_width, colors.red)],
        ["Anxiety", make_bar(anx_width, colors.orange)],
        ["Well-being", make_bar(norm_width, colors.green)]
    ]

    graph_table = Table(graph_data, colWidths=[120, 300])
    graph_table.setStyle([('GRID', (0,0), (-1,-1), 0.3, colors.grey)])

    content.append(graph_table)
    content.append(Spacer(1, 20))

    # ---------- SUMMARY ----------
    content.append(Paragraph("<b>Assessment Summary</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    summary_data = [
        ["Depression Level", res['dep_level']],
        ["Anxiety Level", res['anx_level']],
        ["Risk Level", res['risk']]
    ]

    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.beige),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))

    content.append(summary_table)
    content.append(Spacer(1, 20))

    # ---------- INTERPRETATION ----------
    content.append(Paragraph("<b>Clinical Interpretation</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    content.append(Paragraph(
        f"<b>Depression Level:</b> {res['dep_level']}<br/>"
        f"<b>Anxiety Level:</b> {res['anx_level']}<br/>"
        f"<b>Overall Risk:</b> {res['risk']}<br/><br/>"
        f"The assessment indicates presence of {res['dep_level'].lower()} depressive symptoms "
        f"and {res['anx_level'].lower()} anxiety symptoms. "
        f"These findings suggest a classification of <b>{res['risk']}</b>.",
        styles["Normal"]
    ))
    content.append(Spacer(1, 20))
    
    #QUESTIONS
    content.append(PageBreak())

    content.append(Paragraph("<b>Detailed Questionnaire Responses</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    sorted_responses = sorted(
        res['responses'].items(),
        key=lambda x: int(x[0].split()[1])
    )

    for q, ans in sorted_responses:
        q_num = int(q.split()[1])
        question = QUESTIONS[q_num - 1] if q_num - 1 < len(QUESTIONS) else "N/A"

        content.append(Paragraph(f"<b>Q{q_num}:</b> {question}", styles["Normal"]))
        content.append(Paragraph(f"Response: {ans}", styles["Normal"]))
        content.append(Spacer(1, 8))

    # ---------- FOOTER ----------
    content.append(Paragraph(
        "<i>This report is for screening purposes only and not a clinical diagnosis.</i>",
        styles["Normal"]
    ))

    # ---------- BUILD ----------
    doc.build(content, onFirstPage=draw_border, onLaterPages=draw_border)

    return send_file(file_path, as_attachment=True)

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)