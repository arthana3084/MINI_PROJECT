from flask import Flask, render_template, request
import pickle
import re

app = Flask(__name__)

# Load ML model
model = pickle.load(open("model.pkl", "rb"))
vectorizer = pickle.load(open("vectorizer.pkl", "rb"))

# ---------------- PREPROCESS ----------------
def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    return text

# ---------------- CATEGORY DETECTION ----------------
def detect_category(text):
    text = text.lower()

    if any(w in text for w in ["anxious", "panic", "worried", "stress", "nervous"]):
        return "anxiety"
    elif any(w in text for w in ["sad", "depressed", "hopeless", "low", "tired"]):
        return "depression"
    else:
        return "general"

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/text")
def text():
    return render_template("text.html")

@app.route("/checklist_text", methods=["POST"])
def checklist_text():
    text = request.form.get("user_input", "")
    category = detect_category(text)
    return render_template("checklist.html", text=text, category=category)

@app.route("/checklist_general")
def checklist_general():
    return render_template("checklist.html", text="", category="general")

# ---------------- PREDICTION ----------------
@app.route("/predict", methods=["POST"])
def predict():

    text = request.form.get("text", "")
    category = detect_category(text)

    # -------- ML Prediction --------
    processed = preprocess(text)
    vector = vectorizer.transform([processed])
    probs = model.predict_proba(vector)[0]

    depression = probs[0] * 100
    anxiety = probs[1] * 100
    normal = probs[2] * 100

    # -------- CHECKLIST SCORING --------
    dep_score = 0
    anx_score = 0
    pos_score = 0

    total_questions = len(request.form) - 1  # excluding text field

    for i in range(1, total_questions + 1):
        val = int(request.form.get(f"q{i}", 0))

        weight = 2 if val >= 3 else 1

        if category == "depression":
            dep_score += val * weight

        elif category == "anxiety":
            anx_score += val * weight

        else:
            # general mix
            if i <= total_questions * 0.33:
                pos_score += val * weight
            elif i <= total_questions * 0.66:
                anx_score += val * weight
            else:
                dep_score += val * weight

    # -------- HARD FIX (IMPORTANT) --------
    total_input_score = dep_score + anx_score + pos_score

    if total_input_score == 0:
        return render_template(
            "result.html",
            depression=0,
            anxiety=0,
            normal=100,
            final="Normal"
        )

    # -------- NORMALIZE CHECKLIST --------
    max_score = total_questions * 4 * 2

    if max_score == 0:
        max_score = 1

    dep_score = (dep_score / max_score) * 100
    anx_score = (anx_score / max_score) * 100
    pos_score = (pos_score / max_score) * 100

    # -------- COMBINE ML + CHECKLIST --------
    depression = 0.3 * depression + 0.7 * dep_score
    anxiety = 0.3 * anxiety + 0.7 * anx_score
    normal = 0.3 * normal + 0.7 * pos_score

    # -------- DOMINANCE CONTROL --------
    if dep_score > anx_score and dep_score > pos_score:
        anxiety *= 0.6
        normal *= 0.6

    elif anx_score > dep_score and anx_score > pos_score:
        depression *= 0.6
        normal *= 0.6

    elif pos_score > dep_score and pos_score > anx_score:
        depression *= 0.6
        anxiety *= 0.6

    # -------- FINAL NORMALIZATION --------
    total = depression + anxiety + normal
    if total == 0:
        total = 1

    depression = round((depression / total) * 100, 2)
    anxiety = round((anxiety / total) * 100, 2)
    normal = round((normal / total) * 100, 2)

    # -------- FINAL LABEL --------
    if depression > anxiety and depression > normal:
        final = "Depression"
    elif anxiety > depression and anxiety > normal:
        final = "Anxiety"
    else:
        final = "Normal"

    return render_template(
        "result.html",
        depression=depression,
        anxiety=anxiety,
        normal=normal,
        final=final
    )

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)