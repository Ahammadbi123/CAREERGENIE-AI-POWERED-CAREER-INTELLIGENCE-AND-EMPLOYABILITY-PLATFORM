from groq import Groq
import os
import re
from dotenv import load_dotenv

load_dotenv()


def clean_resume(text):
    """Remove markdown symbols from AI output"""
    text = re.sub(r"#", "", text)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"---", "", text)
    return text.strip()


def calculate_ats_score(resume):
    """Simple ATS score calculation"""

    keywords = [
        "python", "flask", "machine learning", "ai",
        "data", "api", "sql", "git", "javascript"
    ]

    score = 0
    resume_lower = resume.lower()

    for word in keywords:
        if word in resume_lower:
            score += 10

    return min(score, 100)


def calculate_job_match(resume, job_role):

    resume = resume.lower()
    job_role = job_role.lower()

    role_keywords = {
        "ai": ["python", "machine learning", "deep learning", "ai"],
        "web developer": ["html", "css", "javascript", "flask", "react"],
        "data scientist": ["python", "pandas", "sql", "analysis"],
        "game developer": ["c++", "unity", "unreal", "game", "graphics", "c#"]
    }

    keywords = role_keywords.get(job_role, [])

    match = 0

    for word in keywords:
        if word in resume:
            match += 20

    return min(match, 100)


def optimize_resume(data):

    resume_text = data.get("resumeText")
    experience = data.get("experience")
    job_role = data.get("jobRole", "ai")

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""
You are a professional ATS Resume Writer.

Create a clean ONE PAGE professional resume.

Important rules:
- Maximum one page
- No explanations
- No notes
- Only resume content
- ATS friendly format

Resume structure must be EXACT:

NAME

Phone | Email | LinkedIn | Location

PROFESSIONAL SUMMARY
2-3 lines summary based on job role: {job_role}

TECHNICAL SKILLS
Bullet points

EDUCATION

INTERNSHIP EXPERIENCE

PROJECTS

CERTIFICATIONS

STRENGTHS

Candidate experience level:
{experience}

Resume data:
{resume_text}
"""

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )

        optimized_resume = clean_resume(
            response.choices[0].message.content
        )

        ats_score = calculate_ats_score(optimized_resume)
        job_match = calculate_job_match(optimized_resume, job_role)

        return {
            "optimized_resume": optimized_resume,
            "ats_score": ats_score,
            "job_match": job_match
        }

    except Exception as e:
        print("Groq Error:", e)

        return {
            "error": str(e)
        }