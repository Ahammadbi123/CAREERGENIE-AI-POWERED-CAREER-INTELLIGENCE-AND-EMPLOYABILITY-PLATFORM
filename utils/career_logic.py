def calculate_scores(data):
    score = 0

    # Skills
    if len(data["skills"]) >= 5:
        score += 20
    elif len(data["skills"]) >= 3:
        score += 10

    # Projects
    if data["projects"] >= 3:
        score += 20
    elif data["projects"] >= 1:
        score += 10

    # Coding
    if data["coding"] >= 200:
        score += 20
    elif data["coding"] >= 50:
        score += 10

    # Resume
    if data["resume"] == "good":
        score += 20
    elif data["resume"] == "average":
        score += 10

    # Communication
    if data["communication"] == "good":
        score += 20
    elif data["communication"] == "average":
        score += 10

    # Final Scores
    reputation = score
    visibility = int(score * 0.8)

    # Level
    if score >= 80:
        level = "Advanced"
    elif score >= 50:
        level = "Intermediate"
    else:
        level = "Beginner"

    # Suggestions
    suggestions = []

    if data["coding"] < 100:
        suggestions.append("Practice more coding problems")

    if data["projects"] < 2:
        suggestions.append("Build more real-world projects")

    if data["communication"] != "good":
        suggestions.append("Improve communication skills")

    if data["resume"] != "good":
        suggestions.append("Improve your resume")

    return {
        "reputation": reputation,
        "visibility": visibility,
        "level": level,
        "suggestions": suggestions
    }