/* Panic Counseling Chat – frontend logic (text + voice + bot TTS)
   v11: Web Speech API 제거 → MediaRecorder + inline TTS only */

// --------------------------------------------------
// GLOBAL STATE
// --------------------------------------------------
let isWaiting   = false;
let session_id  = null;
let mediaRecorder = null;
let audioChunks   = [];
let isRecording   = false;

// --------------------------------------------------
// CONFIG
// --------------------------------------------------
const HOVER_CLASS  = "hover:bg-gray-200";
const RECORD_CLASS = "bg-red-300";
const PH_LISTENING = "듣고 있어요…";
const PH_DEFAULT   = "Type your message...";

// --------------------------------------------------
// DOM SHORTCUTS
// --------------------------------------------------
const $box  = () => document.getElementById("user-input");
const $btn  = () => document.getElementById("mic-button");
const $chat = () => document.getElementById("chat-box");

// --------------------------------------------------
// TTS (inline)  ------------------------------------
// --------------------------------------------------
const ttsCache = new Map();
async function playTTS(text) {
  if (!text.trim()) return;
  if (ttsCache.has(text)) return new Audio(ttsCache.get(text)).play();
  try {
    const res = await fetch(`/tts?text=${encodeURIComponent(text)}`);
    if (!res.ok) throw new Error(res.status);
    const buf = await res.arrayBuffer();
    const url = URL.createObjectURL(new Blob([buf], { type: res.headers.get("Content-Type") || "audio/mpeg" }));
    ttsCache.set(text, url);
    new Audio(url).play();
  } catch (e) { console.error("TTS fetch error", e); }
}

// --------------------------------------------------
// RECORDING UI -------------------------------------
// --------------------------------------------------
function setRecordUI(rec) {
  isRecording = rec;
  $btn().classList.toggle(RECORD_CLASS, rec);
  $btn().classList.toggle(HOVER_CLASS, !rec);
  $box().placeholder = rec ? PH_LISTENING : ($box().value.trim() ? $box().placeholder : PH_DEFAULT);
}

// --------------------------------------------------
// MEDIARECORDER (server‑side ASR) ONLY --------------
// --------------------------------------------------
async function startMediaRecorder() {
  if (location.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(location.hostname)) {
    alert("마이크는 HTTPS(또는 localhost)에서만 사용 가능합니다.");
    return false;
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true }).catch(e => { alert(e.message); return null; });
  if (!stream) return false;

  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
  mediaRecorder.onstop = async () => {
    setRecordUI(false);
    const blob = new Blob(audioChunks, { type: "audio/webm" });
    audioChunks = [];
    const fd = new FormData();
    fd.append("file", blob, "speech.webm");
    try {
      const r = await fetch("/speech-to-text", { method: "POST", body: fd });
      const { transcript } = await r.json();
      if (transcript) $box().value = transcript;
    } catch (err) { console.error("ASR upload error", err); }
  };

  mediaRecorder.start();
  setRecordUI(true);
  return true;
}

async function toggleRecording() {
  if (!isRecording && !$box().disabled) $box().value = "";
  if (!mediaRecorder) await startMediaRecorder();
  else if (mediaRecorder.state === "recording") mediaRecorder.stop();
  else { mediaRecorder.start(); setRecordUI(true); }
}

// --------------------------------------------------
// CHAT ---------------------------------------------
// --------------------------------------------------
function appendMessage(role, msg, suppressTTS = false) {
  const cls = role === "user" ? "user-msg self-end" : "bot-msg";
  const who = role === "user" ? "You" : "Bot";
  $chat().insertAdjacentHTML("beforeend", `<div class="${cls}"><strong>${who}:</strong> ${msg}</div>`);
  $chat().scrollTop = $chat().scrollHeight;
  if (role === "bot" && !suppressTTS) playTTS(msg);
}

function handleKey(e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!e.repeat) sendMessage(); } }

async function sendMessage() {
  const msg = $box().value.trim(); if (!msg || isWaiting) return; isWaiting = true;
  const sendBtn = document.getElementById("send-button");
  [$box(), sendBtn].forEach(el => { el.disabled = true; el.style.opacity = 0.6; });

  appendMessage("user", msg);
  const loadId = `load-${Date.now()}`;
  $chat().insertAdjacentHTML("beforeend", `<div id="${loadId}" class="bot-msg italic text-gray-500">Bot is typing<span class="typing-dots"></span></div>`);
  $box().value = ""; $box().placeholder = PH_DEFAULT;

  try {
    const res = await fetch("/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id, user_utterance: msg }) });
    const data = await res.json();
    document.getElementById(loadId).remove();
    appendMessage("bot", data.system_utterance);
    if (!data.end_signal) {
      [$box(), sendBtn].forEach(el => { el.disabled = false; el.style.opacity = 1; });
      $box().focus();
    } else {
      $box().placeholder = "상담이 종료되었습니다.";
      document.getElementById("restart-button").classList.remove("hidden");
    }
  } catch (err) {
    console.error(err);
    document.getElementById(loadId).innerText = "⚠️ 오류";
    [$box(), sendBtn].forEach(el => { el.disabled = false; el.style.opacity = 1; });
  }
  isWaiting = false;
}

function resetSession() { sessionStorage.removeItem("session_id"); location.reload(); }

// --------------------------------------------------
// BOOTSTRAP ----------------------------------------
// --------------------------------------------------
window.onload = async () => {
  session_id = sessionStorage.getItem("session_id");
  if (!session_id) {
    session_id = (await (await fetch("/init-session", { method: "POST" })).json()).session_id;
    sessionStorage.setItem("session_id", session_id);
  }

  const dm = await (await fetch("/default-message")).json();
  $box().value = dm.default_message; $box().placeholder = PH_DEFAULT;

if ((await (await fetch("/status")).json()).ready)
  appendMessage("bot", "안녕하세요, 공황 응급 지원입니다. 어떻게 도와드릴까요?", true);
};
