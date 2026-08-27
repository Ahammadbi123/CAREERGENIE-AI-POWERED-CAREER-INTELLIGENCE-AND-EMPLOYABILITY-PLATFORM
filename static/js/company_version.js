async function updateCompany() {

    const company = document.getElementById("company-name").value;

    try {
        const response = await fetch("/update_company", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ company: company })
        });

        if (!response.ok) {
            alert("Update failed. Status: " + response.status);
            return;
        }

        const data = await response.json();
        console.log("Update response:", data);

        alert("Company updated successfully!");
        location.reload();

    } catch (error) {
        console.error("Error:", error);
        alert("Something went wrong. Check console.");
    }
}


async function previousVersion() {

    const company = document.getElementById("company-name").value;

    try {
        const response = await fetch("/previous_company", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ company: company })
        });

        if (!response.ok) {
            alert("Previous failed. Status: " + response.status);
            return;
        }

        const data = await response.json();

        if (data.status === "previous") {
            alert("Moved to previous version");
            location.reload();
        } else {
            alert("No older version available");
        }

    } catch (error) {
        console.error("Error:", error);
        alert("Something went wrong. Check console.");
    }
}