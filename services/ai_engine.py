def analyze_jobs(jobs, skills):
    results = []

    for job in jobs:
        score = 0

        for skill in skills:
            if skill.lower() in job['title'].lower():
                score += 1

        job['match'] = score * 25
        results.append(job)

    return sorted(results, key=lambda x: x['match'], reverse=True)