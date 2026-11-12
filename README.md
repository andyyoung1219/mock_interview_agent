
# Adaptive Mock Interview Agent

An adaptive mock interview agent built with LangGraph,
Gemini API, FastAPI, JavaScript, and SQLite.

## Overview

本專案為 AI Agent 課程作業，提供研究所推甄與企業求職
兩種文字模擬面試。

系統根據個人背景與回答內容動態提問，透過 LangGraph
決定 FOLLOW_UP、NEXT_TOPIC 或 FINISH，並在面試
結束後提供 Gemini 生成的回饋摘要。

## Features

- 研究所推甄、企業求職面試
- 自訂面試難度
- PDF / DOCX 文件解析與檢索
- 多回合動態提問與有限追問
- SQLite 歷史紀錄、恢復與刪除
- 面試結束後產生具回答證據的摘要
- 防止重複提交、SQLite 版本衝突檢查
- Podman 單容器部署

## Architecture

Frontend (HTML/CSS/JavaScript)
  -> FastAPI
  -> LangGraph Agent
      -> Gemini API
      -> Document Parser / Retrieval
  -> SQLite

## Requirements

- Python 3.13
- Podman
- Gemini API Key

## Run Locally

1. 建立 Python 虛擬環境。

   python -m venv .venv

2. 啟動虛擬環境（Windows）。

   .\.venv\Scripts\Activate.ps1

3. 安裝套件。

   python -m pip install -r requirements.txt

4. 建立 .env，設定：

   GEMINI_API_KEY=your_api_key
   GEMINI_MODEL=your_model_name

5. 啟動 FastAPI。

   python -m uvicorn server:app --reload

6. 開啟 http://127.0.0.1:8000

## Podman Deployment

建立映像檔：

    podman build -t interview-agent:hw2 .

建立 Volume：

    podman volume create interview-data

啟動容器（PowerShell 單行指令）：

    podman run -d --name interview-agent --env-file .env -e INTERVIEW_DB_PATH=/app/data/interviews.db -p 127.0.0.1:8000:8000 -v interview-data:/app/data:U interview-agent:hw2

檢查容器：

    podman ps
    podman logs interview-agent

網站位址：

    http://127.0.0.1:8000

## Tests

執行離線測試：

    python -m unittest discover -s tests -p "test_hw2.py" -v

整合測試結果記錄於：

    tests/test_results.md

## Data Persistence

SQLite 用來保存會話 State、歷史問答及摘要。
資料庫由 INTERVIEW_DB_PATH 指定。

Podman 使用 Named Volume 保存資料，
避免容器重建造成面試紀錄遺失。

## Limitations

- 作業二以文字面試為主
- 不支援正式錄取或聘用結果預測
- AI 回饋僅供面試練習參考
- Gemini API 需要網路與有效額度
- 歷史 API 尚未提供使用者登入驗證
- 公開部署前需加入存取控制

## Security

API Key 使用 .env，且不得提交 GitHub。
本機資料庫與上傳文件亦不得提交版本控制。

## Author

National Taipei University
Department of Computer Science and Information Engineering
