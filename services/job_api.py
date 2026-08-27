import requests
import os

def fetch_adzuna(role):

    app_id = os.getenv("ADZUNA_APP_ID")
    api_key = os.getenv("ADZUNA_APP_KEY")

    url = f"https://api.adzuna.com/v1/api/jobs/in/search/1?app_id={app_id}&app_key={api_key}&what={role}"

    try:
        response = requests.get(url)

        if response.status_code != 200:
            return []

        try:
            data = response.json()
        except:
            return []

        jobs = []

        for job in data.get('results', []):

            title = job.get('title', '').lower()

            # 🔥 qualification logic
            if "engineer" in title:
                qualification = "B.Tech / B.E"
            elif "analyst" in title:
                qualification = "Any Graduate"
            elif "manager" in title:
                qualification = "MBA Preferred"
            else:
                qualification = "Any Graduate"

            jobs.append({
                "title": job.get('title', 'No Title'),
                "company": job.get('company', {}).get('display_name', 'Unknown'),
                "apply": job.get('redirect_url', '#'),

                "location": job.get('location', {}).get('area', ['India'])[0] if job.get('location') else "India",
                "id": job.get('id', 'N/A'),

                "package": (
                    f"{int(job.get('salary_min',0)/100000)} - {int(job.get('salary_max',0)/100000)} LPA"
                    if job.get('salary_min') else "Not disclosed"
                ),

                "qualification": qualification
            })

        return jobs   # ✅ INSIDE function

    except Exception as e:
        print("Error:", e)
        return []     # ✅ INSIDE function