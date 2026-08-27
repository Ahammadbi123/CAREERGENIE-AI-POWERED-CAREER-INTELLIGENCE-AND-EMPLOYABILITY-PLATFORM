def calculate_employability(data):

    score = 0
    gaps = []
    suggestions = []

    # Skills
    skills = len(data["skills"])
    if skills >= 5:
        score += 25
    elif skills >= 3:
        score += 15
        suggestions.append("Try to learn 2-3 more advanced technologies")
    else:
        gaps.append("Improve technical skills")
        suggestions.append("Learn Python, DSA, DBMS fundamentals")

    # Projects
    if data["projects"] >= 3:
        score += 25
    elif data["projects"] >= 1:
        score += 15
        suggestions.append("Build 1-2 advanced projects with real-world use cases")
    else:
        gaps.append("Build real-world projects")
        suggestions.append("Create projects like AI chatbot, portfolio, or web apps")

    # Coding
    if data["coding"] >= 200:
        score += 25
    elif data["coding"] >= 50:
        score += 15
        suggestions.append("Solve more DSA problems on LeetCode / HackerRank")
    else:
        gaps.append("Practice coding problems")
        suggestions.append("Start with 50+ problems (arrays, strings, basics)")

    # Communication
    if data["communication"] == "good":
        score += 15
    else:
        gaps.append("Improve communication skills")
        suggestions.append("Practice speaking, mock interviews, English fluency")

    # Resume
    if data["resume"] == "good":
        score += 10
    else:
        gaps.append("Improve your resume")
        suggestions.append("Use ATS-friendly format and add measurable achievements")

    # Level
    if score >= 80:
        level = "Advanced"
        suggestions.append("Start applying for top product-based companies")
    elif score >= 50:
        level = "Intermediate"
        suggestions.append("Focus on DSA + projects to reach advanced level")
    else:
        level = "Beginner"
        suggestions.append("Build strong basics before applying to jobs")

    percent = min(95, score + 5)

    # Final AI Summary (🔥 highlight feature)
    if level == "Advanced":
        summary = "You are industry-ready! Focus on cracking top-tier interviews."
    elif level == "Intermediate":
        summary = "You are on the right track. Improve key areas to become job-ready."
    else:
        summary = "You need strong fundamentals and practice to become employable."

    return {
        "score": score,
        "level": level,
        "gaps": gaps,
        "suggestions": suggestions,
        "percent": percent,
        "summary": summary
    }