

import logging

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from uuid import uuid4

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.agent.graph import build_graph
from src.agent.summary import generate_summary
from src.tools.document import parse_document

from src.storage.sqlite_store import (
    SQLiteStore,
    SessionConflict,
)

app = FastAPI(title="Adaptive Interview Agent")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)

agent = build_graph()

# SQLite 持久化儲存
store = SQLiteStore()


class StartRequest(BaseModel):
    interview_type: Literal["graduate", "job"]
    difficulty: Literal["easy", "medium", "hard"]
    background: str = Field(min_length=1, max_length=10000)
    max_topics: int = Field(default=3, ge=1, le=6)


class AnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(min_length=1, max_length=10000)


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


MAX_UPLOAD_BYTES = 10 * 1024 * 1024

@app.post("/api/start")
async def start_interview(
    interview_type: Literal["graduate", "job"] = Form(...),
    difficulty: Literal["easy", "medium", "hard"] = Form(...),
    background: str = Form(""),
    max_topics: int = Form(3, ge=1, le=6),
    file: UploadFile | None = File(None),
):
    session_id = str(uuid4())

    background = background.strip()
    document_chunks = []
    uploaded_filename = None

    # ===== 1. 驗證文字背景 =====

    if len(background) > 10000:
        raise HTTPException(
            status_code=422,
            detail="個人背景不可超過 10000 字元"
        )

    # ===== 2. 解析使用者上傳的文件 =====

    if file is not None:
        original_name = file.filename or ""
        extension = Path(original_name).suffix.lower()

        if extension not in {".pdf", ".docx"}:
            await file.close()
            raise HTTPException(
                status_code=415,
                detail="僅支援 PDF / DOCX 文件"
            )

        try:
            # 使用暫存目錄，避免上傳檔案永久保留
            with TemporaryDirectory() as temp_dir:
                temp_path = (
                    Path(temp_dir) / f"upload{extension}"
                )

                total_size = 0

                with temp_path.open("wb") as output:
                    while True:
                        chunk = await file.read(1024 * 1024)

                        if not chunk:
                            break

                        total_size += len(chunk)

                        if total_size > MAX_UPLOAD_BYTES:
                            raise HTTPException(
                                status_code=413,
                                detail="文件不可超過 10 MB"
                            )

                        output.write(chunk)

                if total_size == 0:
                    raise HTTPException(
                        status_code=422,
                        detail="上傳的文件是空白檔案"
                    )

                # 執行現有的 PDF / DOCX Tool
                parsed = await run_in_threadpool(
                    parse_document,
                    str(temp_path)
                )

        finally:
            await file.close()

        if not parsed["ok"]:
            raise HTTPException(
                status_code=422,
                detail=parsed["message"]
            )

        # 只保留檔名，不使用使用者提供的路徑
        uploaded_filename = Path(
            original_name.replace("\\", "/")
        ).name[:128]

        document_chunks = parsed["data"]["chunks"]

        # 將暫存檔名改為原始文件名稱，供檢索追蹤
        for chunk in document_chunks:
            chunk["doc_id"] = uploaded_filename

    # ===== 3. 確認至少有一種背景資料 =====

    if not background and not document_chunks:
        raise HTTPException(
            status_code=422,
            detail="請輸入個人背景或上傳文件"
        )

    # 只有文件時，使用文件前段文字作為初始背景
    if not background and document_chunks:
        background = "使用者文件前段摘錄：\n" + (
            "\n".join(
                item["text"]
                for item in document_chunks[:4]
            )[:1500]
        )

    # ===== 4. 建立 LangGraph State =====

    state = {
        "interview_type": interview_type,
        "difficulty": difficulty,
        "background": background,

        "topic_index": 0,
        "topic": "",
        "question": "",
        "latest_answer": "",

        "question_history": [],
        "answer_history": [],

        "followup_count": 0,
        "max_followups": 1,
        "max_topics": max_topics,

        "suggestion": "",
        "decision": "INITIAL",
        "decision_reason": "",
        "missing_point": "",
        "status": "active",

        "document_chunks": document_chunks,
        "retrieved_context": [],
        "tool_log": [],
    }

    # ===== 5. 執行 LangGraph =====

    try:
        result = await run_in_threadpool(
            agent.invoke,
            state
        )

    except Exception:
        logging.exception("面試啟動失敗")
        raise HTTPException(
            status_code=502,
            detail="Agent 啟動失敗，請稍後重試"
        )

    # ===== 6. 成功後保存 Session =====

    try:
        await run_in_threadpool(
            store.create_session,
            session_id,
            result
        )
    except Exception:
        logging.exception("面試 Session 儲存失敗")
        raise HTTPException(
            status_code=500,
            detail="面試已生成，但資料儲存失敗，請重新建立面試"
        )

    # ===== 7. 回傳給前端 =====

    retrieved = result.get("retrieved_context", [])

    return {
        "session_id": session_id,
        "status": result["status"],
        "topic": result["topic"],
        "question": result["question"],

        "document": (
            {
                "filename": uploaded_filename,
                "chunk_count": len(document_chunks),
            }
            if uploaded_filename else None
        ),

        "retrieval": {
            "match_count": len(retrieved),
            "sources": [
                {
                    "doc_id": item["doc_id"],
                    "source": item["source"],
                }
                for item in retrieved
            ],
        },
    }



@app.post("/api/answer")
async def answer_interview(request: AnswerRequest):
    stored = await run_in_threadpool(
        store.load_session,
        request.session_id
    )

    state = stored["state"] if stored else None

    if state is None:
        raise HTTPException(
            status_code=404,
            detail="找不到面試 Session"
        )

    if state["status"] == "finished":
        raise HTTPException(
            status_code=400,
            detail="面試已經結束"
        )

    if not request.answer.strip():
        raise HTTPException(
            status_code=422,
            detail="回答不可為空白"
        )

    new_state = {
        **state,
        "latest_answer": request.answer.strip()
    }

    try:
        result = await run_in_threadpool(
            agent.invoke, new_state
        )
    except Exception:
        logging.exception("面試回答處理失敗")
        raise HTTPException(
            status_code=502,
            detail="Agent 處理失敗，原本面試進度已保留"
        )

    # 只有成功才更新 State
    try:
        await run_in_threadpool(
            store.update_session,
            request.session_id,
            result,
            stored["version"]
        )

    except SessionConflict:
        raise HTTPException(
            status_code=409,
            detail="面試已有新的進度，請重新載入"
        )

    except Exception:
        logging.exception("面試進度儲存失敗")
        raise HTTPException(
            status_code=500,
            detail="資料庫儲存失敗，請重新載入確認進度"
        )

    return {
        "status": result["status"],
        "topic": result["topic"],
        "question": result["question"],
        "decision": result["decision"],
        "reason": result["decision_reason"]
    }

@app.get("/api/sessions")
async def list_interviews():
    return await run_in_threadpool(
        store.list_sessions
    )


@app.get("/api/sessions/{session_id}")
async def get_interview(session_id: str):
    stored = await run_in_threadpool(
        store.load_session,
        session_id
    )

    if stored is None:
        raise HTTPException(
            status_code=404,
            detail="找不到面試 Session"
        )

    state = stored["state"]

    turns = await run_in_threadpool(
        store.get_turns,
        session_id
    )

    return {
        "session_id": session_id,
        "status": state["status"],
        "topic": state["topic"],
        "question": state["question"],
        "decision": state["decision"],
        "turns": turns,
        "version": stored["version"],
    }


@app.delete("/api/sessions/{session_id}")
async def delete_interview(session_id: str):
    deleted = await run_in_threadpool(
        store.delete_session,
        session_id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="找不到面試 Session"
        )

    return {"message": "面試紀錄已刪除"}


@app.get("/api/sessions/{session_id}/summary")
async def get_interview_summary(session_id: str):
    stored = await run_in_threadpool(
        store.load_session, session_id
    )

    if stored is None:
        raise HTTPException(
            status_code=404,
            detail="找不到面試 Session"
        )

    if stored["state"]["status"] != "finished":
        raise HTTPException(
            status_code=409,
            detail="面試尚未完成"
        )

    summary = await run_in_threadpool(
        store.get_summary, session_id
    )

    return {"summary": summary}


@app.post("/api/sessions/{session_id}/summary")
async def create_interview_summary(session_id: str):
    stored = await run_in_threadpool(
        store.load_session, session_id
    )

    if stored is None:
        raise HTTPException(
            status_code=404,
            detail="找不到面試 Session"
        )

    if stored["state"]["status"] != "finished":
        raise HTTPException(
            status_code=409,
            detail="面試尚未完成"
        )

    # 已有摘要就直接回傳，不重複呼叫 Gemini
    existing = await run_in_threadpool(
        store.get_summary, session_id
    )

    if existing is not None:
        return {"summary": existing}

    try:
        summary = await run_in_threadpool(
            generate_summary,
            stored["state"]
        )
    except Exception:
        logging.exception("面試摘要生成失敗")
        raise HTTPException(
            status_code=502,
            detail="摘要生成失敗，面試紀錄已保留，可稍後重試"
        )

    try:
        saved = await run_in_threadpool(
            store.save_summary,
            session_id,
            summary
        )
    except Exception:
        logging.exception("面試摘要儲存失敗")
        raise HTTPException(
            status_code=500,
            detail="摘要儲存失敗，請重新嘗試"
        )

    return {"summary": saved}
