function optimizeResume() {

    const resumeText = document.getElementById("resumeText").value;
    const experience = document.getElementById("experience").value;

    const outputDiv = document.getElementById("resumeOutput");
    const atsScore = document.getElementById("atsScore");
    const jobMatch = document.getElementById("jobMatch");

    if (!resumeText.trim()) {
        alert("Please paste your resume!");
        return;
    }

    outputDiv.innerText = "Optimizing resume... Please wait.";

    fetch("/optimize-genai-universal", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            resumeText: resumeText,
            experience: experience,
            jobRole: "ai"
        })
    })
    .then(response => {

        if (!response.ok) {
            throw new Error("Server error: " + response.status);
        }

        return response.json();
    })
    .then(data => {

        if (data.optimized_resume) {

            // Show Resume
            outputDiv.innerText = data.optimized_resume;

            // Show ATS score
            if (data.ats_score !== undefined) {
                atsScore.innerText = data.ats_score + "%";
            }

            // Show Job Match score
            if (data.job_match !== undefined) {
                jobMatch.innerText = data.job_match + "%";
            }

        } 
        else if (data.error) {

            outputDiv.innerText = "Error: " + data.error;

        } 
        else {

            outputDiv.innerText = "Unexpected response from server.";

        }

    })
    .catch(error => {

        console.error("Error:", error);
        outputDiv.innerText = "Something went wrong. Check console.";

    });
}