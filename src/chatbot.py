from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from pydantic import BaseModel
import threading
import json
# from simple_history import History
from logger import Logger
from checker import Checker
from collections import defaultdict
import os
from datetime import datetime
from uuid import uuid4
# from simple_panic import Panic
import pdb
from model import CounselorAgent
import secrets
from cachetools import TTLCache
from pathlib import Path


session_histories = TTLCache(maxsize=1000, ttl=1800)
# config 로딩

# FastAPI 앱 초기화
app = FastAPI()


# ──────────────────────────────────────────────
# Path setup
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent            # .../repo_root/src
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
LOG_DIR = BASE_DIR / "logs"
DIAL_DIR = BASE_DIR / "dials"

# ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
DIAL_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# FastAPI mounts
# ──────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# ✅ 모델 로딩 상태 체크 API
@app.get("/status")
async def get_status():
    return {"ready": app.state.model_ready}

# ✅ 기본 메시지 API
@app.get("/default-message")
async def get_default_message():
    return {"default_message": "지금 카페인데 사람이 너무 많아요 어지럽고 메스꺼워요.. 어떡하죠?"} 


# ✅ 백그라운드 CounselingAPI 로딩 함수
def load_counselor(app: FastAPI):
    config_path = os.environ.get("CONFIG_PATH", "./demo_chat_config_kor.json")
    demo_config = json.load(open(config_path, "r", encoding="utf-8"))
    log_path_cfg = demo_config["log_path"]
    log_path = (LOG_DIR / log_path_cfg) if not Path(log_path_cfg).is_absolute() else Path(log_path_cfg)
    logger = Logger(log_path)
    logger.log_and_print("Loading CounselingAPI with configuration...")
    app.state.config = demo_config
    app.state.logger = logger
    app.state.model_ready = True  
    app.state.model = CounselorAgent(
        demo_config, logger=logger,
    )
    logger.log_and_print("CounselingAPI loaded successfully.")
    return True


# ✅ lifespan에서 thread 시작
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model_ready = False
    threading.Thread(target=load_counselor, args=(app,)).start()
    yield

app.router.lifespan_context = lifespan


# ✅ 모델 준비 상태에 따라 index 또는 로딩 페이지 반환
@app.get("/", response_class=HTMLResponse)
async def get_main(request: Request):
    if not app.state.model_ready:
        return templates.TemplateResponse("loading.html", {"request": request})
    return templates.TemplateResponse("index.html", {"request": request})

def save_and_clear_session(session_id: str, history: list[dict]):
    logger = app.state.logger

    log_path = DIAL_DIR / f"{session_id}.json"        # ✅ 절대경로

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    logger.log_and_print(f"Session {session_id} saved to {log_path}")

    # 세션 히스토리 삭제
    del session_histories[session_id]
    logger.log_and_print(f"Session {session_id} cleared from memory.")
    
    
def save_turn_log(session_id: str, history: list[dict]):
    logger = app.state.logger
    log_path = DIAL_DIR / f"{session_id}.json"        # ✅ 절대경로

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    logger.log_and_print(f"Turn log for session {session_id} saved to {log_path}")
    
# ✅ 채팅 처리
class ChatRequest(BaseModel):
    session_id: str
    user_utterance: str
    
class ChatResponse(BaseModel):
    system_utterance: str
    end_signal: bool = False
@app.post("/chat", response_model=ChatResponse)

async def chat(request: Request, req: ChatRequest):
    config      = request.app.state.config
    session_id  = req.session_id
    model       = request.app.state.model
    logger      = request.app.state.logger

    # ── 1. initialize state if needed ───────────────────────────────
    if (
        session_id not in session_histories
        or session_histories[session_id] is None
    ):
        session_histories[session_id] = {
            "cnt": 0,                      # will bump right away
            "history": [
                {"role": "Counselor", "message": config["first_words"]}
            ],
        }

    # ── 2. append client utterance ─────────────────────────────────
    session_histories[session_id]["history"].append(
        {"role": "Client", "message": req.user_utterance}
    )
    logger.log_and_print(
        f"Session {session_id}: {req.user_utterance}"
    )
    
    # ── 3. generate counselor reply ────────────────────────────────
    cnt   = session_histories[session_id]["cnt"] + 1  # next turn index
    hist  = session_histories[session_id]["history"]

    system_utt = model.generate( hist)
    logger.log_and_print(
        f"Session {session_id}: {system_utt}"
    )
    
    # ── [종료 신호 처리] ──────────────────────────────────────────
    if "상담" in system_utt and "종료" in system_utt:
        farewell = config["last_words"]     # ← 고정 멘트
        hist.append({"role": "Counselor", "message": farewell})

        # ① 마지막 턴 로그 저장
        save_turn_log(session_id, hist)

        # ② 전체 세션 저장 & 메모리 정리
        save_and_clear_session(session_id, hist)

        # ③ 프런트엔드에 종료 알림
        return ChatResponse(
            system_utterance=farewell,
            end_signal=True
        )
        
    else:
        hist.append({"role": "Counselor", "message": system_utt})

    # update counters
    session_histories[session_id]["cnt"] = cnt

    # ── 4. SAVE LOG FOR THIS TURN  ---------------------------------
    save_turn_log(session_id, hist)

    # ── 5. reply to frontend ───────────────────────────────────────
    return ChatResponse(system_utterance=system_utt, end_signal=False)

@app.post("/init-session")
async def init_session():
    
    config = app.state.config
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand      = secrets.token_hex(4)   
    session_id =  f"{timestamp}_{rand}"
    logger = app.state.logger
    
    history = []
    history.append({"role": "Counselor", "message": config["first_words"]})
    session_histories[session_id] = {'cnt' : 1, 'history' : history}
    logger.log_and_print(f"Session initialized: {session_id}")
    logger.log_and_print(f"Session {session_id} initialized with first words: {config['first_words']}")
    return {"session_id": session_id, "system_utterance":  config["first_words"], 'end_signal': False}