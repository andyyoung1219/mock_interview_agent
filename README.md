# Adaptive Mock Interview Agent

AI Agent 課程作業二的文字模擬面試系統，提供研究所推甄與企業求職兩種情境。系統使用 FastAPI、LangGraph、Gemini API 和 SQLite，並提供 Podman 容器部署方式。

## 目前功能

- 可選擇面試類型與難度，填寫文字背景或上傳一份 PDF／DOCX。單一檔案上限為 10 MiB，PDF 上限為 20 頁。若 PDF 沒有文字層，請先做 OCR，或改為填寫文字背景。
- Gemini 依背景和相關文件片段出題，並分析每回合的回答。LangGraph 依分析結果和目前狀態決定追問（`FOLLOW_UP`）、換題（`NEXT_TOPIC`）或結束（`FINISH`）。網頁固定選用 3 個主題，API 支援 1 至 6 個，每個主題最多追問一次。
- SQLite 保存面試狀態、問答與摘要，可從歷史紀錄載入並繼續未完成的面試。提交回答時，系統按 `submission_id` 識別已處理的請求，並用 SQLite 版本號防止舊進度覆寫新進度。
- 面試結束後可生成回饋摘要。系統核對優點與改進項目引用的文字是否出現在對應回合的回答中。

## Agent 設計

本專案採用 **State-based decision**，而非自由形式的 ReAct。面試有固定階段與明確的結束條件，由程式規則控制流程，比讓 LLM 自行選擇工具更容易預測與測試。

```text
初始：select_topic → retrieve_documents → generate_question → 等待使用者回答
回答：analyze_answer → decide_action
        ├─ FOLLOW_UP   → prepare_followup → retrieve_documents → generate_question
        ├─ NEXT_TOPIC  → next_topic → select_topic → retrieve_documents → generate_question
        └─ FINISH      → finish_interview（status = "finished"）
```

Gemini 只負責產生問題與分析回答（`suggestion`、`reason`、`missing_point`），最終動作由 `decide_action` 依追問次數與主題上限決定。

### Tools

兩個工具皆為實際執行的 Python 函式，由 Graph 或 API 在固定時機呼叫，不是 Gemini 的 function calling。

| Tool | 位置 | 用途 |
| --- | --- | --- |
| `parse_document` | `src/tools/document.py` | 解析 PDF／DOCX，切成每段 1000 字元、帶來源標記的文字片段。 |
| `retrieve_context` | `src/tools/retrieval.py` | 以關鍵詞評分檢索與目前主題相關的片段（不使用 embedding 或向量資料庫）。 |

兩個工具都回傳 `ok`、`data`、`error_code`、`message`，失敗時以錯誤碼說明原因（例如 `NO_TEXT`、`FILE_TOO_LARGE`、`EMPTY_QUERY`）。

## 專案結構

| 路徑 | 用途 |
| --- | --- |
| `frontend/` | 顯示面試問題、提交回答、載入歷史及顯示回饋摘要。 |
| `server.py` | 驗證輸入、處理上傳、執行 Agent，並提供會話與摘要 API。 |
| `src/tools/document.py` | FastAPI 在啟動面試前呼叫 `parse_document`，將文件切成帶有來源標記的文字片段。 |
| `src/agent/graph.py`、`src/tools/retrieval.py` | LangGraph 執行狀態流程，出題前用 `retrieve_context` 做關鍵詞檢索，並呼叫 Gemini 產題或分析回答。 |
| `src/agent/summary.py`、`src/storage/sqlite_store.py` | 分別負責生成與核對摘要，以及保存會話、問答、提交結果和摘要。 |
| `run_agent.py` | 命令列版本，使用預設背景與記憶體狀態，沒有 SQLite 歷史與摘要功能。 |
| `tests/` | unittest 測試（決策規則、文件解析、檢索、SQLite 儲存）。 |
| `Containerfile` | Podman／容器建置檔。 |

## 環境設定

需要 Python 3.13（與容器基底映像一致）和一組可用的 Gemini API 金鑰。

在專案根目錄複製 `.env.example` 為 `.env`，並填入下列設定：

| 變數 | 說明 |
| --- | --- |
| `GEMINI_API_KEY` | Gemini API 金鑰。 |
| `GEMINI_MODEL` | 模型名稱。原始碼沒有預設值，必須填入你的帳號可使用的模型。 |
| `INTERVIEW_DB_PATH` | SQLite 檔案路徑。`.env.example` 的 `/app/data/interviews.db` 是容器內路徑，本機執行時請改為本機路徑（見下方）。 |


## 本機執行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:INTERVIEW_DB_PATH = "$PWD\data\interviews.db"
.\.venv\Scripts\python.exe -m uvicorn server:app --reload
```

瀏覽器開啟 `http://127.0.0.1:8000`。若要使用命令列版本，執行 `python run_agent.py`。

## 測試

在專案根目錄執行：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_hw2 tests.test_sqlite_store
```

測試使用暫存資料庫與虛構文件，不會動到既有的 `data/interviews.db`，也不呼叫 Gemini。`tests/test_document.py` 與 `tests/test_retrieval.py` 為直接執行的腳本，可用 `python -m tests.test_document` 個別執行。

測試只涵蓋決策規則、文件解析、檢索、持久化與摘要引文核對。尚未進行真實 Gemini 連線、回答品質評量與瀏覽器端操作測試。

## API 摘要

| 端點 | 說明 |
| --- | --- |
| `GET /api/health` | 服務健康檢查。 |
| `POST /api/start` | 以 multipart 表單啟動面試：`interview_type`、`difficulty`、`background`、`max_topics`、可選 `file`。上傳檔案格式或大小不符時分別回傳 415、413、422。 |
| `POST /api/answer` | JSON：`session_id`、`answer`、`submission_id`。同一個 `submission_id` 重複提交會回傳已保存的結果。Gemini 失敗或輸出格式錯誤時回傳 502，原有進度保持不變。 |
| `GET /api/sessions` | 列出歷史會話。 |
| `GET /api/sessions/{id}` | 讀取目前題目、狀態、版本與問答。 |
| `GET`／`POST /api/sessions/{id}/summary` | 讀取／生成回饋摘要。面試未完成時回傳 409。 |
| `DELETE /api/sessions/{id}` | 刪除會話（目前尚未完成，見「已知限制」）。 |

## 已知限制

- `POST /api/answer` 的 `submission_id` 目前實際上是必填。省略時 `server.py` 會因變數 `previous` 未賦值而回傳 500；內建前端會自動產生此欄位，直接呼叫 API 時請每個新回答都傳入 8 至 80 字元的 `submission_id`。
- `DELETE /api/sessions/{id}` 已宣告路由，但 `SQLiteStore` 尚未實作 `delete_session`，因此刪除功能無法使用，`tests.test_sqlite_store` 也會因此失敗。
- 文件解析不含 OCR，只支援有文字層的 PDF 與 DOCX。
- `retrieve_context` 為詞彙比對，不理解語意；同義詞或跨語言查詢可能找不到相關片段。
- 資料庫保存背景、文件片段與回答內容，部署時請妥善保護。

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

容器以非 root 使用者（UID 10001）執行，`:U` 參數讓該使用者可寫入掛載的 Volume。`--env-file .env` 會把金鑰傳入容器，請勿把 `.env` 打包進映像（已列入 `.containerignore`）。

常用管理指令：

```powershell
podman stop interview-agent      # 停止
podman rm interview-agent        # 移除容器（Volume 內的資料會保留）
podman volume rm interview-data  # 刪除資料（無法復原）
```