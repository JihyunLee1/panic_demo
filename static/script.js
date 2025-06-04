let isWaiting = false;

let session_id = null;


window.onload = async function () {
  // ✅ 세션 ID 초기화
  session_id = sessionStorage.getItem("session_id");
  if (!session_id) {
    console.log("세션 ID가 없습니다. 새로운 세션을 초기화합니다.");
    const res = await fetch("/init-session", { method: "POST" });
    const data = await res.json();
    session_id = data.session_id;
    sessionStorage.setItem("session_id", session_id);
  }

  // 기본 메시지 초기화
  const response = await fetch("/default-message");
  const data = await response.json();
  document.getElementById("user-input").value = data.default_message;

  const status = await fetch("/status");
  const ready = await status.json();
  if (ready) {
    appendMessage("bot", "안녕하세요, 공황 응급 지원입니다. 어떻게 도와드릴까요?");
  }
};

function handleKey(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!event.repeat) sendMessage();
  }
}

function appendMessage(role, message) {
  const chatBox = document.getElementById("chat-box");
  const className = role === "user" ? "user-msg self-end" : "bot-msg";
  const sender = role === "user" ? "You" : "Bot";
  chatBox.innerHTML += `<div class="${className}"><strong>${sender}:</strong> ${message}</div>`;
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
  if (isWaiting) return;
  isWaiting = true;

  const inputBox = document.getElementById("user-input");
  const sendButton = document.getElementById("send-button");
  const chatBox = document.getElementById("chat-box");
  const message = inputBox.value.trim();
  if (!message) {
    isWaiting = false;
    return;
  }

  inputBox.disabled = true;
  sendButton.disabled = true;
  inputBox.style.opacity = 0.6;
  sendButton.style.opacity = 0.5;

  appendMessage("user", message);

  const loadingId = `loading-${Date.now()}`;
  chatBox.innerHTML += `<div id="${loadingId}" class="bot-msg typing-dots text-gray-500 italic">Bot is typing<span class="typing-dots"></span></div>`;
  inputBox.value = "";
  session_id = sessionStorage.getItem("session_id");
  console.log(session_id);

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({session_id: session_id, user_utterance: message}),
    });

    const data = await response.json();
    const loadingElem = document.getElementById(loadingId);
    if (loadingElem) {
      loadingElem.outerHTML = `<div class="bot-msg"><strong>Bot:</strong> ${data.system_utterance}</div>`;
    }

    if (!data.end_signal) {
      inputBox.disabled = false;
      sendButton.disabled = false;
      inputBox.style.opacity = 1;
      sendButton.style.opacity = 1;
      inputBox.focus();
    } else {
      inputBox.placeholder = "상담이 종료되었습니다.";
      document.getElementById("restart-button").classList.remove("hidden");
    }
  } catch (err) {
    const loadingElem = document.getElementById(loadingId);
    if (loadingElem) {
      loadingElem.outerHTML = `<div class="text-red-500">⚠️ 오류가 발생했습니다.</div>`;
    }
    inputBox.disabled = false;
    sendButton.disabled = false;
    inputBox.style.opacity = 1;
    sendButton.style.opacity = 1;
  }

  isWaiting = false;
  chatBox.scrollTop = chatBox.scrollHeight;
}

function resetSession() {
  sessionStorage.removeItem("session_id");
  location.reload();
}