from flask import Blueprint, render_template, request
from groq import Groq
import re
import os
from dotenv import load_dotenv

load_dotenv()

resume_bp = Blueprint("resume", __name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


@resume_bp.route("/resume-builder")
def resume_form():
    return render_template("resume_form.html")


@resume_bp.route("/generate-resume", methods=["POST"])
def generate_resume():

    # ===== Basic Info =====
    name = request.form.get('name') or ""
    email = request.form.get('email') or ""
    phone = request.form.get('phone') or ""
    linkedin = request.form.get('linkedin') or ""
    github = request.form.get('github') or ""
    portfolio = request.form.get('portfolio') or ""

    # ===== Sections (FIXED) =====
    summary = request.form.get('summary') or ""
    education = request.form.get('education') or ""
    skills = request.form.get('skills') or ""
    projects = request.form.get('projects') or ""
    experience = request.form.get('experience') or ""
    internships = request.form.get('internships') or ""
    certifications = request.form.get('certifications') or ""
    achievements = request.form.get('achievements') or ""
    additional_info = request.form.get('additional_info') or ""

    # 🔥 PROMPT (CLEAN)
    prompt = f"""
Generate a clean ATS resume in HTML.

RULES:
- Use <h1> for name
- Use <p> for contact
- Use <h3> for headings
- Use <ul><li> for content
- No styling, no CSS
- No empty sections

STRUCTURE:

<h1>NAME</h1>
<p>Phone | Email | LinkedIn | GitHub | Portfolio</p>
<hr>

<h3>SUMMARY</h3>
<ul><li>...</li></ul>
<hr>

Continue same format.

DATA:

Name: {name}
Phone: {phone}
Email: {email}
LinkedIn: {linkedin}
GitHub: {github}
Portfolio: {portfolio}

Summary:
{summary}

Education:
{education}

Skills:
{skills}

Projects:
{projects}

Experience:
{experience}

Internships:
{internships}

Certifications:
{certifications}

Achievements:
{achievements}

Additional Info:
{additional_info}
"""

    # 🔥 API CALL
    response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": prompt}]
)

    resume_text = response.choices[0].message.content.strip()

    # =========================
    # 🔥 FORMAT FIXES
    # =========================

    # Ensure <h1>
    if "<h1>" not in resume_text:
        resume_text = f"<h1>{name}</h1>" + resume_text

    # Center name
    resume_text = re.sub(
        r"<h1.*?>(.*?)</h1>",
        r"<h1 style='text-align:center;font-size:18px;font-weight:bold;'>\1</h1>",
        resume_text,
        flags=re.IGNORECASE
    )

    # Contact line fix
    contact_line = f"{phone} | {email} | {linkedin} | {github} | {portfolio}"

    if "<p>" not in resume_text:
        resume_text = resume_text.replace(
            "</h1>",
            f"</h1><p style='text-align:center;'>{contact_line}</p>"
        )

    # 🔥 Remove empty sections
    resume_text = re.sub(
        r"<h3>.*?</h3>\s*(<ul>\s*</ul>|<p>\s*</p>)\s*<hr>",
        "",
        resume_text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Remove unwanted phrases
    unwanted = [
        "No experience listed",
        "No achievements listed",
        "No certifications listed",
        "No additional information"
    ]

    for u in unwanted:
        resume_text = resume_text.replace(u, "")

    # Remove empty UL
    resume_text = re.sub(r"<ul>\s*</ul>", "", resume_text)

    # Fix HR
    resume_text = re.sub(r"(<hr>\s*){2,}", "<hr>", resume_text)

    return render_template("resume_preview.html", resume=resume_text)