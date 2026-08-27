from flask import Blueprint, render_template, request, jsonify
from genai_modules.universal_resume_engine import optimize_resume

genai_universal_resume_bp = Blueprint(
    "genai_universal_resume",
    __name__
)


# Page render
@genai_universal_resume_bp.route("/genai-universal-resume")
def genai_universal_resume_page():
    return render_template("genai_universal_resume.html")


# Resume optimization API
@genai_universal_resume_bp.route("/optimize-genai-universal", methods=["POST"])
def optimize_genai_universal():

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "No data received"
            }), 400

        resume_text = data.get("resumeText")

        if not resume_text or resume_text.strip() == "":
            return jsonify({
                "error": "Resume text is empty"
            }), 400

        # Call AI resume optimizer
        result = optimize_resume(data)

        if "error" in result:
            return jsonify(result), 500

        return jsonify({
            "optimized_resume": result.get("optimized_resume"),
            "ats_score": result.get("ats_score"),
            "job_match": result.get("job_match")
        })

    except Exception as e:

        print("Universal Resume Error:", e)

        return jsonify({
            "error": "Server error occurred"
        }), 500