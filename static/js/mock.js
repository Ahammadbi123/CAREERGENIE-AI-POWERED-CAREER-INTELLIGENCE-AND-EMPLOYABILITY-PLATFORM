console.log("mock.js loaded");

const chatArea = document.getElementById("chatArea");
const messageBox = document.getElementById("message");

const askAI = document.getElementById("askAI");
const askGenAI = document.getElementById("askGenAI");
const clearBtn = document.getElementById("clearBtn");
const copyBtn = document.getElementById("copyBtn");
const voiceBtn = document.getElementById("voiceBtn");
const pdfBtn = document.getElementById("pdfBtn");
const toast = document.getElementById("toast");

/* ---------- TOAST ---------- */
function showToast(text) {
    toast.innerText = text;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 1500);
}

/* ---------- ADD MESSAGE ---------- */
function addMessage(text, type) {
    const div = document.createElement("div");
    div.className = type === "user" ? "user-msg" : "bot-msg";
    div.innerText = text;
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
}

/* ---------- SEND MESSAGE ---------- */
function sendMessage(mode) {
    const msg = messageBox.value.trim();

    if (!msg) {
        showToast("Speak or type a message");
        return;
    }

    addMessage(msg, "user");
    messageBox.value = "";

    const formData = new FormData();
    formData.append("message", msg);
    formData.append("mode", mode);

    fetch("/get_reply", {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        addMessage(data.reply || "No reply", "bot");
    })
    .catch(() => {
        addMessage("Server error", "bot");
    });
}

/* ---------- BUTTON EVENTS ---------- */
askAI.onclick = () => sendMessage("ai");
askGenAI.onclick = () => sendMessage("genai");

clearBtn.onclick = () => {
    chatArea.innerHTML = "";
};

copyBtn.onclick = () => {
    navigator.clipboard.writeText(chatArea.innerText);
    showToast("Copied ✓");
};

/* ======================================================
   🎤 SPEAK → TEXT (VOICE INPUT)
====================================================== */

let recognition;

if ("webkitSpeechRecognition" in window) {
    recognition = new webkitSpeechRecognition();
    recognition.lang = "en-IN";   // Telugu kavali ante "te-IN"
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
        showToast("Listening...");
    };

    recognition.onresult = (event) => {
        const spokenText = event.results[0][0].transcript;
        messageBox.value = spokenText;   // ✅ VOICE → TEXT
        showToast("Voice captured");
    };

    recognition.onerror = () => {
        showToast("Voice error");
    };

    voiceBtn.onclick = () => {
        recognition.start();
    };

} else {
    voiceBtn.disabled = true;
    voiceBtn.innerText = "Mic not supported";
}

/* ---------- DOWNLOAD PDF ---------- */
pdfBtn.onclick = () => {
    const text = chatArea.innerText.trim();
    if (!text) {
        showToast("Nothing to download");
        return;
    }

    const formData = new FormData();
    formData.append("chat", text);

    fetch("/download_chat_pdf", {
        method: "POST",
        body: formData
    })
    .then(res => res.blob())
    .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "chat.pdf";
        a.click();
        URL.revokeObjectURL(url);
    });
};
