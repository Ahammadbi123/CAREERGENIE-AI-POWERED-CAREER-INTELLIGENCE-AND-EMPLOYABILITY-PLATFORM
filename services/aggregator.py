from services.job_api import fetch_adzuna

def get_all_jobs(role):
    jobs = fetch_adzuna(role)

    if not jobs:
        return [{
            "title": "No jobs found",
            "company": "Try different role",
            "apply": "#"
        }]

    return jobs[:10]