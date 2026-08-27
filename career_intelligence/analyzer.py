# analyzer.py

from collections import Counter
from career_intelligence.extractor import SkillExtractor


class CompanyAnalyzer:

    def __init__(self):
        self.extractor = SkillExtractor()

    def analyze_company(self, company_data, total_companies):

        description = company_data["description"]
        extracted = self.extractor.extract_skills(description)

        all_skills = []
        for category in extracted.values():
            all_skills.extend(category)

        skill_counts = Counter(all_skills)

        # Hiring Weightage Logic (Rule-Based Intelligence)
        weightage = {
            "Programming": 25,
            "DSA": 20 if "algorithms" in all_skills else 10,
            "OOPS": 10 if "oops" in all_skills else 5,
            "SQL": 10 if "sql" in all_skills else 5,
            "Cloud": 15 if any(s in all_skills for s in ["aws", "azure", "gcp"]) else 5,
            "Communication": 10 if "communication" in all_skills else 5,
            "Problem Solving": 20 if "problem solving" in description.lower() else 10
        }

        total_mentions = sum(skill_counts.values()) or 1

        percentages = {
            skill: round((count / total_mentions) * 100, 2)
            for skill, count in skill_counts.items()
        }

        # Demand Level Logic
        if len(skill_counts) > 6:
            demand_level = "Very High"
        elif len(skill_counts) > 4:
            demand_level = "High"
        else:
            demand_level = "Moderate"

        # Core / High / Emerging Classification
        core = [skill for skill, pct in percentages.items() if pct >= 20]
        high = [skill for skill, pct in percentages.items() if 10 <= pct < 20]
        emerging = [skill for skill, pct in percentages.items() if pct < 10]

        hiring_dna = list(skill_counts.keys())[:5]

        return {
            "Company Name": company_data["company"],
            "Company Type": company_data["type"],
            "Core Technology Base": "Scalable Software Systems" if company_data["type"] == "Product" else "Client Service Solutions",
            "Technology Domains Used": list(extracted.keys()),
            "Required Programming Languages": extracted.get("programming_languages", []),
            "Required Technical Skills": all_skills,
            "Required Soft Skills": extracted.get("soft_skills", []),
            "AI Extracted Hiring DNA": hiring_dna,
            "Most Repeated Requirements": hiring_dna,
            "Hiring Base Logic": "Algorithmic Strength & Scalability Focus" if company_data["type"] == "Product" else "Client Delivery & Adaptability Focus",
            "Hiring Weightage Model": weightage,
            "Demand Level": demand_level,
            "Core Required Skills (80%+)": core,
            "High Demand Skills (50–80%)": high,
            "Emerging Skills (<50%)": emerging,
            "Skill Percentage Distribution": percentages
        }