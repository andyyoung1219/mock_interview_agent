
# Adaptive Mock Interview Agent

AI Agent 課程作業二的文字模擬面試系統，提供研究所推甄與企業求職兩種情境。系統使用 FastAPI、LangGraph、Gemini API 和 SQLite，並提供 Podman 容器部署方式。

## 目前功能

- 可選擇面試類型與難度，填寫文字背景或上傳一份 PDF／DOCX。單一檔案上限為 10 MiB，PDF 上限為 20 頁。若 PDF 沒有文字層，請先做 OCR，或改為填寫文字背景。
- Gemini 依背景和相關文件片段出題，並分析每回合的回答。LangGraph 依分析結果和目前狀態決定追問（`FOLLOW_UP`）、換題（`NEXT_TOPIC`）或結束（`FINISH`）。網頁固定選用 3 個主題，API 支援 1 至 6 個，每個主題最多追問一次。
- SQLite 保存面試狀態、問答與摘要，可從歷史紀錄載入並繼續未完成的面試。提交回答時，系統按 `submission_id` 識別已處理的請求，並用 SQLite 版本號防止舊進度覆寫新進度。
- 面試結束後可生成回饋摘要。系統核對優點與改進項目引用的文字是否出現在對應回合的回答中。

## 程式架構

| 元件 | 用途 |
| --- | --- |
| `frontend/` | 顯示面試問題、提交回答、載入歷史及顯示回饋摘要。 |
| `server.py` | 驗證輸入、處理上傳、執行 Agent，並提供會話與摘要 API。 |
| `src/tools/document.py` | FastAPI 在啟動面試前呼叫 `parse_document`，將文件切成帶有來源標記的文字片段。 |
| `src/agent/graph.py`、`src/tools/retrieval.py` | LangGraph 執行狀態流程，出題前用 `retrieve_context` 做關鍵詞檢索，並呼叫 Gemini 產題或分析回答。 |
| `src/agent/summary.py`、`src/storage/sqlite_store.py` | 分別負責生成與核對摘要，以及保存會話、問答、提交結果和摘要。 |

## Podman 部署

Windows 請先啟動已建立的 Podman machine（`podman machine start`）。在專案根目錄設定好 `.env`，再執行以下指令。

```powershell
podman build -t interview-agent:hw2 .
podman volume create interview-data
podman run -d --name interview-agent --env-file .env -e INTERVIEW_DB_PATH=/app/data/interviews.db -p 127.0.0.1:8000:8000 -v interview-data:/app/data:U interview-agent:hw2
podman ps
podman logs interview-agent
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

前端與後端由同一個容器提供，網頁位址為 `http://127.0.0.1:8000`。容器使用 `interview-data` Named Volume 保存 SQLite 資料。重建容器時可掛載同一個 Volume 以保留資料。上傳檔案在處理後會清除，擷取的文字片段則隨會話狀態存入 SQLite。

