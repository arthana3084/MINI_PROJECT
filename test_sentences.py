import app

sentences = [
    "I feel quite low today",
    "Im so worried about the exam",
    "Everything seems pointless and I have no energy",
    "I feel nervous all the time",
    "Nothing matters anymore",
    "Just having a normal day today",
    "I am constantly overthinking things and going crazy",
    "I feel exhausted, sad and crying every night"
]

print("--- Testing Sentences ---")
for s in sentences:
    res = app.predict_category(s)
    print(f"'{s}' => {res}")
