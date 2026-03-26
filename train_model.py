import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import pickle

# Load dataset
df = pd.read_csv("dataset.csv")   # change if your file name is different

# Print column names (to debug)
print("Columns in dataset:", df.columns)

# Rename columns (IMPORTANT)
df = df.rename(columns={
    "statement": "text",
    "status": "label",
    "Statement": "text",
    "Status": "label"
})

# Check data
print("\nSample Data:")
print(df.head())

# Ensure required columns exist
if "text" not in df.columns or "label" not in df.columns:
    print("❌ ERROR: Column names not found correctly")
    exit()

# Remove missing values
df = df.dropna(subset=["text", "label"])

# Split features and labels
X = df["text"]
y = df["label"]

# Convert text to numerical features
vectorizer = TfidfVectorizer(max_features=5000)
X_vec = vectorizer.fit_transform(X)

# Train model
model = LogisticRegression(max_iter=200)
model.fit(X_vec, y)

# Save model and vectorizer
pickle.dump(model, open("model.pkl", "wb"))
pickle.dump(vectorizer, open("vectorizer.pkl", "wb"))

print("\n✅ Model trained and saved successfully!")