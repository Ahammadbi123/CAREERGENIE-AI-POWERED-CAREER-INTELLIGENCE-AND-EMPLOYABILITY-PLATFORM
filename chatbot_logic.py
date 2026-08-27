import json
import os

# Base directory (MAIN PROJECT)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data folder path
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_reply(question):
    question = question.lower().strip()

    # Telugu check (only when user asks)
    telugu = False
    if "telugu" in question:
        telugu = True
        question = question.replace("telugu", "").strip()

    # ---------------- SUBJECT DETECTION ----------------
    if "python" in question:
        data = load_json("python.json")

    elif "java" in question:
        data = load_json("java.json")

    elif "sql" in question:
        data = load_json("sql.json")

    elif "c++" in question or "cpp" in question:
        data = load_json("c++.json")

    elif question.startswith("c ") or " c " in question or question.endswith(" c"):
        data = load_json("c.json")

    else:
        return "Sorry 🙂 Subject not identified."

    # ---------------- KEYWORD MATCH ----------------
    for key in data:
        if key in question:
            return data[key]["te"] if telugu else data[key]["en"]

    return "Sorry 🙂 Ee question knowledge base lo ledu."
