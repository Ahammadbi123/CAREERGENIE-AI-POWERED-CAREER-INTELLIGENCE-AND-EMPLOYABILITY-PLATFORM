# market_intelligence.py

from collections import Counter


def aggregate_market_data(company_reports):

    global_counter = Counter()

    for company in company_reports:
        for skill in company["Skill Percentage Distribution"]:
            global_counter[skill] += 1

    total_companies = len(company_reports)

    demand_percentage = {
        skill: round((count / total_companies) * 100, 2)
        for skill, count in global_counter.items()
    }

    sorted_skills = dict(sorted(demand_percentage.items(), key=lambda x: x[1], reverse=True))

    return {
        "Top 10 Most Demanded Skills": list(sorted_skills.keys())[:10],
        "Demand Percentage": sorted_skills,
        "Core Skills": [s for s, p in sorted_skills.items() if p >= 70],
        "High Demand Skills": [s for s, p in sorted_skills.items() if 40 <= p < 70],
        "Emerging Skills": [s for s, p in sorted_skills.items() if p < 40]
    }