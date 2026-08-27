// ==========================
// 🎥 Webcam Start
// ==========================
navigator.mediaDevices.getUserMedia({ video: true, audio: true })
.then(stream => {
    const video = document.getElementById("webcam");
    if (video) {
        video.srcObject = stream;
        video.play();
    }
})
.catch(err => {
    console.error("Camera error:", err);
});


// ==========================
// 🤖 Speak Function
// ==========================
function speak(text) {
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "en-IN";
    speech.rate = 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(speech);
}


// ==========================
// ⏳ TIMER SYSTEM
// ==========================
let timerInterval = null;
let TOTAL_TIME = 300;

function startTimer() {

    if (timerInterval) clearInterval(timerInterval);

    let timeLeft = TOTAL_TIME;
    updateTimerDisplay(timeLeft);

    timerInterval = setInterval(() => {

        timeLeft--;
        updateTimerDisplay(timeLeft);

        if (timeLeft === 30) {
            alert("⚠️ Only 30 seconds left!");
        }

        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            alert("⏰ Time up! Please click Submit.");
        }

    }, 1000);
}

function updateTimerDisplay(seconds) {
    let minutes = Math.floor(seconds / 60);
    let remainingSeconds = seconds % 60;

    if (remainingSeconds < 10) remainingSeconds = "0" + remainingSeconds;

    const timerElement = document.getElementById("timer");
    if (timerElement) {
        timerElement.innerText = minutes + ":" + remainingSeconds;
    }
}



// ==========================
// 🚀 Start / Next Question
// ==========================
function startInterview() {

    let company = document.getElementById("companySelect")?.value || "General";
    let type = document.getElementById("interviewType")?.value || "hr";

    fetch(`/generate_question?round=${type}&company=${company}`)
    .then(res => res.json())
    .then(data => {

        if (data.completed) {
            window.location.href = "/final-result";
            return;
        }

        document.getElementById("question").innerText = data.question;
        document.getElementById("feedback").innerHTML = "";
        document.getElementById("answerBox").value = "";

        let counter = document.getElementById("questionNumber");
        if (counter) {
            let current = parseInt(counter.innerText) || 0;
            if (current < 5) counter.innerText = current + 1;
        }

        speak(data.question);
        startTimer();
    })
    .catch(err => {
        console.log("Error fetching question:", err);
    });
}


// ==========================
// 📤 Submit Answer
// ==========================
let submitting = false;

function submitAnswer() {

    if (submitting) return;
    submitting = true;

    const question = document.getElementById("question").innerText;
    const answer = document.getElementById("answerBox").value;

    if (!answer.trim()) {
        document.getElementById("feedback").innerHTML =
            "⚠️ Please enter your answer.";
        submitting = false;
        return;
    }

    document.getElementById("feedback").innerHTML =
        "⏳ Evaluating your answer...";

    fetch("/receive_answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, answer })
    })
    .then(res => res.json())
    .then(data => {

        document.getElementById("feedback").innerHTML =
            "<h3>📝 AI Feedback</h3>" +
            "<div style='white-space: pre-line;'>" +
            data.feedback +
            "</div>";

        submitting = false;

        let progress = (data.question_count / 5) * 100;
        let progressBar = document.getElementById("progressBar");
        if (progressBar) progressBar.style.width = progress + "%";

        if (data.question_count >= 5) {
            window.location.href = "/final-result";
        }

    })
    .catch(() => {
        document.getElementById("feedback").innerHTML =
            "❌ Error sending answer.";
        submitting = false;
    });
}


// ==========================
// 🎤 ADVANCED VOICE SYSTEM
// ==========================
let recognition;
let isListening = false;

function startAnswer() {

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        alert("Speech Recognition not supported in this browser.");
        return;
    }

    const button = document.querySelector(".answer-btn");
    const answerBox = document.getElementById("answerBox");

    if (!recognition) {
        recognition = new SpeechRecognition();
        recognition.lang = "en-IN";
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
    }

    if (!isListening) {

        recognition.start();
        isListening = true;
        button.innerText = "⛔ Stop";

        let finalTranscript = "";

        recognition.onresult = function (event) {

            let interimTranscript = "";

            for (let i = event.resultIndex; i < event.results.length; i++) {

                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript + " ";
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            answerBox.value = finalTranscript + interimTranscript;
        };

        recognition.onerror = function (event) {
            console.log("Voice error:", event.error);
        };

        recognition.onend = function () {
            isListening = false;
            button.innerText = "🎤 Voice";
        };

    } else {

        recognition.stop();
        isListening = false;
        button.innerText = "🎤 Voice";
    }
}

