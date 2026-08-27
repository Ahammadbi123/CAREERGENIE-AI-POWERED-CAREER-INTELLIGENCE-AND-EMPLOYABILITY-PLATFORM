let skillChart = null;
let currentSkills = [];

/* ===============================
   🔹 Render Skills (Cards Display)
=================================*/
function renderSkills(data, modeLabel) {
    const container = document.getElementById("skillsContainer");
    container.innerHTML = `<p id="modeLabel" style="
        font-weight:bold;
        color:#22c55e;
        font-size:1.1rem;
        margin-bottom:20px;
        border-left: 4px solid #22c55e;
        padding-left:10px;
        text-shadow:0 0 10px #22c55e;
    ">${modeLabel}</p>`;

    if (!Array.isArray(data)) {
        container.innerHTML += "<p style='color:red;'>Invalid Data Format from Server</p>";
        return;
    }

    currentSkills = data;
    applyFilter();
}

/* ===============================
   🔽 Apply Filter (UI UPGRADED)
=================================*/
function applyFilter() {
    const selected = document.getElementById("categoryFilter").value;
    const container = document.getElementById("skillsContainer");
    
    const modeLabel = document.getElementById("modeLabel") ? document.getElementById("modeLabel").outerHTML : "";
    container.innerHTML = modeLabel;

    let filtered = currentSkills;
    if (selected !== "All") {
        filtered = currentSkills.filter(s => s.category === selected);
    }

    filtered.forEach((skill, index) => {
        const name = skill.name || skill.skill || "Unknown Skill";
        const demand = skill.demand || 0;
        const salary = skill.salary || "N/A";

        // 🎨 Dynamic colors
        const colors = ["#00f2fe", "#2563eb", "#7c3aed", "#22c55e", "#f59e0b"];
        const glow = colors[index % colors.length];

        container.innerHTML += `
            <div style="
                background: linear-gradient(145deg, rgba(10,20,40,0.95), rgba(2,6,23,0.98));
                padding:20px;
                margin-bottom:20px;
                border-radius:18px;
                border:1px solid ${glow}55;
                box-shadow:0 0 25px ${glow}33, inset 0 0 20px ${glow}22;
                transition: all 0.4s ease;
                position:relative;
                overflow:hidden;
            "
            onmouseover="this.style.transform='translateY(-8px) scale(1.02)'"
            onmouseout="this.style.transform='translateY(0px)'"
            >

                <!-- Glow Border -->
                <div style="
                    position:absolute;
                    inset:0;
                    border-radius:18px;
                    padding:1px;
                    background: linear-gradient(45deg, ${glow}, #00f2fe, ${glow});
                    -webkit-mask:
                        linear-gradient(#fff 0 0) content-box,
                        linear-gradient(#fff 0 0);
                    -webkit-mask-composite: xor;
                    mask-composite: exclude;
                    opacity:0.5;
                    animation: borderGlow 4s linear infinite;
                "></div>

                <h3 style="
                    margin:0 0 10px 0;
                    font-size:1.4rem;
                    color:${glow};
                    font-weight:700;
                ">
                    ${name}
                </h3>

                <p style="
                    margin-bottom: 15px;
                    color: #94a3b8;
                    font-size: 0.95rem;
                ">
                    <strong>Category:</strong> ${skill.category || 'General'} |
                    <strong>Salary:</strong> ${salary}
                </p>

                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    margin-bottom:8px;
                ">
                    <span style="
                        font-weight:600;
                        color:#cbd5e1;
                        font-size:0.9rem;
                        text-transform:uppercase;
                    ">
                        Market Demand
                    </span>

                    <span style="
                        font-weight:800;
                        color:${glow};
                        font-size:1.2rem;
                    ">
                        ${demand}%
                    </span>
                </div>

                <div style="
                    background:rgba(255,255,255,0.08);
                    height:12px;
                    border-radius:10px;
                    width:100%;
                    overflow:hidden;
                ">
                    <div style="
                        width:0%;
                        height:100%;
                        background: linear-gradient(90deg, ${glow}, #00f2fe, ${glow});
                        background-size:200% 100%;
                        border-radius:10px;
                        animation: moveBar 3s linear infinite;
                        transition: width 1s ease;
                    " class="progress-bar"></div>
                </div>
            </div>
        `;
    });

    // 🚀 Animate bars after render
    setTimeout(() => {
        document.querySelectorAll(".progress-bar").forEach((bar, i) => {
            bar.style.width = (filtered[i].demand || 0) + "%";
        });
    }, 200);

    updateChart(filtered);
}

/* ===============================
   🤖 AI Generate Function
=================================*/
function generateAI() {
    const role = document.getElementById("roleInput").value;
    const location = document.getElementById("locInput").value;
    const experience = document.getElementById("expInput").value;

    if(!role) { alert("Please enter a role!"); return; }

    fetch("/generate-ai-skills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, location, experience })
    })
    .then(res => res.json())
    .then(data => renderSkills(data, "🤖 AI Generated Skills"))
    .catch(err => console.error(err));
}

/* ===============================
   🔥 Trending Manual Function
=================================*/
function loadTrending() {
    fetch("/generate-trending-skills")
    .then(res => res.json())
    .then(data => renderSkills(data, "🔥 Market Trending Skills"))
    .catch(err => console.error(err));
}

/* ===============================
   📊 Chart Update Function
=================================*/
function updateChart(skills) {
    const canvas = document.getElementById("skillChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (skillChart) skillChart.destroy();

    const topLabelsPlugin = {
        id: 'topLabels',
        afterDatasetsDraw(chart) {
            const { ctx, data, scales: { x, y } } = chart;
            ctx.save();
            ctx.font = 'bold 12px Arial';
            ctx.fillStyle = '#00f2fe';
            ctx.textAlign = 'center';

            data.datasets[0].data.forEach((value, index) => {
                const xPos = x.getPixelForValue(index);
                const yPos = y.getPixelForValue(value) - 8;
                ctx.fillText(value + '%', xPos, yPos);
            });
            ctx.restore();
        }
    };

    skillChart = new Chart(ctx, {
        type: "bar",
        plugins: [topLabelsPlugin],
        data: {
            labels: skills.map(s => s.name || s.skill),
            datasets: [{
                label: "Demand %",
                data: skills.map(s => s.demand),
                backgroundColor: "rgba(0,242,254,0.6)",
                borderColor: "#00f2fe",
                borderWidth: 1,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            layout: { padding: { top: 25 } },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 110,
                    ticks: {
                        color: "#cbd5e1",
                        callback: val => val <= 100 ? val + "%" : ""
                    },
                    grid: { color: "rgba(255,255,255,0.05)" }
                },
                x: {
                    ticks: { color: "#cbd5e1" },
                    grid: { display: false }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}