let sessionId = null;
let busy = false;

// 只在本機瀏覽器記錄最後使用的 Session ID；完整資料仍以 SQLite 為準。
const LAST_SESSION_KEY = "interview_last_session_id";

const startForm = document.getElementById("start-form");
const answerForm = document.getElementById("answer-form");
const chatPanel = document.getElementById("chat-panel");
const setupPanel = document.getElementById("setup-panel");
const messages = document.getElementById("messages");
const topic = document.getElementById("topic");
const statusText = document.getElementById("status");
const startBtn = document.getElementById("start-btn");
const sendBtn = document.getElementById("send-btn");
const answerInput = document.getElementById("answer");
const historyList = document.getElementById("history-list");
const historyStatus = document.getElementById("history-status");
const refreshHistoryBtn = document.getElementById("refresh-history-btn");
const newInterviewBtn = document.getElementById("new-interview-btn");
const reloadSessionBtn = document.getElementById("reload-session-btn");
const summaryPanel =
    document.getElementById("summary-panel");

const summaryContent =
    document.getElementById("summary-content");

const generateSummaryBtn =
    document.getElementById("generate-summary-btn");

function rememberLastSession(id) {
    try {
        if (id) localStorage.setItem(LAST_SESSION_KEY, id);
        else localStorage.removeItem(LAST_SESSION_KEY);
    } catch (_) {
        // 瀏覽器禁止 localStorage 時，仍可透過歷史清單恢復。
    }
}

function readLastSession() {
    try { return localStorage.getItem(LAST_SESSION_KEY); }
    catch (_) { return null; }
}

function setBusy(value) {
    busy = value;

    startBtn.disabled = value;
    sendBtn.disabled = value;
    answerInput.disabled = value;

    if (refreshHistoryBtn) {
        refreshHistoryBtn.disabled = value;
    }

    if (reloadSessionBtn) {
        reloadSessionBtn.disabled = value;
    }

    if (newInterviewBtn) {
        newInterviewBtn.disabled = value;
    }

    if (historyList) {
        historyList.querySelectorAll("button").forEach(button => {
            button.disabled = value;
        });
    }
}

function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = text; // 以文字呈現，不執行 LLM 回傳的 HTML。
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

async function apiRequest(url, options = {}) {
    let response;
    try {
        response = await fetch(url, options);
    } catch (_) {
        throw new Error("無法連線到後端，請確認 FastAPI 是否正在執行");
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = typeof data.detail === "string"
            ? data.detail : `請求失敗 (HTTP ${response.status})`;
        throw new Error(detail);
    }
    return data;
}

async function postAPI(url, data) {
    const isFormData = data instanceof FormData;
    const options = {
        method: "POST",
        body: isFormData ? data : JSON.stringify(data),
    };
    if (!isFormData) options.headers = { "Content-Type": "application/json" };
    return apiRequest(url, options);
}

function setInterviewView(isFinished) {
    // 已完成面試：隱藏不必要的對話元件
    const chatHeader = chatPanel.querySelector(".chat-header");

    chatHeader?.classList.toggle("hidden", isFinished);
    messages.classList.toggle("hidden", isFinished);
    answerForm.classList.toggle("hidden", isFinished);
    statusText.classList.toggle("hidden", isFinished);

    // 已完成面試不需要重新載入進度按鈕
    reloadSessionBtn?.classList.toggle("hidden", isFinished);

    // 進行中的面試不顯示回饋報告
    if (!isFinished) {
        summaryPanel.classList.add("hidden");
    }
}

function renderSummary(summary) {
    summaryPanel.classList.remove("hidden");
    summaryContent.replaceChildren();

    function addText(tag, value, parent = summaryContent) {
        const el = document.createElement(tag);
        el.textContent = value;
        parent.appendChild(el);
        return el;
    }

    addText("h3", "整體表現");
    addText("p", summary.overview);

    const groups = [
        ["回答優點", summary.strengths],
        ["需要加強", summary.improvements]
    ];

    for (const [title, items] of groups) {
        addText("h3", title);

        const ul = document.createElement("ul");
        summaryContent.appendChild(ul);

        if (!items.length) {
            addText("li", "沒有足夠證據可供評估", ul);
        }

        for (const item of items) {
            addText(
                "li",
                `${item.point}
第 ${item.turn_no} 題證據：${item.evidence}`,
                ul
            );
        }
    }

    addText("h3", "改善建議");
    const ul = document.createElement("ul");
    summaryContent.appendChild(ul);

    for (const suggestion of summary.suggestions) {
        addText("li", suggestion, ul);
    }

    generateSummaryBtn.classList.add("hidden");
}


async function loadSummary(id, createIfMissing = false) {
    summaryPanel.classList.remove("hidden");
    summaryContent.textContent = "正在讀取面試摘要...";
    generateSummaryBtn.classList.add("hidden");
    generateSummaryBtn.disabled = true;

    const url =
        `/api/sessions/${encodeURIComponent(id)}/summary`;

    try {
        let result = await apiRequest(url);

        if (!result.summary && createIfMissing) {
            summaryContent.textContent =
                "AI 正在分析整場面試，產生回饋報告...";

            result = await apiRequest(url, {
                method: "POST"
            });
        }

        // 使用者可能已經切換至另一場面試
        if (sessionId !== id) return;

        if (result.summary) {
            renderSummary(result.summary);
        } else {
            summaryContent.textContent =
                "這場面試尚未產生摘要。";

            generateSummaryBtn.classList.remove("hidden");
        }

    } catch (error) {
        if (sessionId !== id) return;

        summaryContent.textContent =
            `摘要讀取或產生失敗：${error.message}`;

        generateSummaryBtn.classList.remove("hidden");
    } finally {
        generateSummaryBtn.disabled = false;
    }
}


function showSetup() {
    setupPanel.classList.remove("hidden");
    chatPanel.classList.add("hidden");
}

function showChat() {
    setupPanel.classList.add("hidden");
    chatPanel.classList.remove("hidden");
}

function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "未知時間";
    return date.toLocaleString("zh-TW", { hour12: false });
}

function prettyInterviewType(value) {
    return value === "graduate" ? "研究所推甄" : value === "job" ? "企業求職" : value;
}

function prettyDifficulty(value) {
    return ({ easy: "簡單", medium: "中等", hard: "困難" })[value] || value;
}

function renderHistory(items) {
    historyList.replaceChildren();
    historyStatus.textContent = items.length === 0 ? "還沒有歷史面試紀錄。" : `共 ${items.length} 場面試`;

    for (const item of items) {
        const row = document.createElement("div");
        row.className = "history-item";

        const main = document.createElement("div");
        main.className = "history-main";
        const title = document.createElement("strong");
        title.textContent = `${prettyInterviewType(item.interview_type)} · ${prettyDifficulty(item.difficulty)}`;
        const meta = document.createElement("small");
        meta.textContent = `${item.status === "finished" ? "已結束" : "進行中"} · 更新於 ${formatDate(item.updated_at)}`;
        main.append(title, meta);

        const actions = document.createElement("div");
        actions.className = "history-actions";
        const openButton = document.createElement("button");
        openButton.type = "button";
        openButton.className = "secondary-btn";
        openButton.textContent = item.status === "finished" ? "查看紀錄" : "繼續面試";
        openButton.addEventListener("click", () => loadSession(item.session_id));

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "danger-btn";
        deleteButton.textContent = "刪除";
        deleteButton.addEventListener("click", () => deleteSession(item.session_id));

        actions.append(openButton, deleteButton);
        row.append(main, actions);
        historyList.appendChild(row);
    }
}

async function refreshHistory() {
    if (!historyStatus || !historyList) {
        console.error("找不到歷史紀錄 HTML 元素");
        return;
    }

    historyStatus.textContent = "正在讀取歷史紀錄...";

    try {
        const items = await apiRequest("/api/sessions", {
            signal: AbortSignal.timeout(10000)
        });

        if (!Array.isArray(items)) {
            throw new Error("API 回傳的格式不是陣列");
        }

        renderHistory(items);

        console.log("成功讀取歷史紀錄：", items.length);

    } catch (error) {
        console.error("歷史紀錄載入失敗：", error);

        historyStatus.textContent =
            `讀取失敗：${error.name === "TimeoutError"
                ? "API 等待逾時（10 秒）"
                : error.message}`;
    }
}

async function loadSession(id) {
    if (busy) return;
    setBusy(true);
    try {
        const record = await apiRequest(`/api/sessions/${encodeURIComponent(id)}`);
        if (!Array.isArray(record.turns)) throw new Error("面試紀錄格式不正確");
        // 等資料成功取得後才變更目前會話，避免載入失敗使原本進度消失。
        sessionId = id;
        rememberLastSession(id);
        messages.replaceChildren();
        summaryPanel.classList.add("hidden");
        summaryContent.replaceChildren();

        for (const turn of record.turns) {
            addMessage(turn.question, "ai");
            addMessage(turn.answer, "user");
        }

        const isFinished = record.status === "finished";
        if (isFinished) {
            addMessage("面試已完成，以上是這次面試的問答紀錄。", "ai");
            statusText.textContent = `已載入完成的面試，共 ${record.turns.length} 回合。`;
        } else {
            if (record.question) addMessage(record.question, "ai");
            statusText.textContent = `已恢復面試，共 ${record.turns.length} 個已回答回合，可以繼續作答。`;
        }
        topic.textContent = isFinished ? "已完成" : record.topic || "目前主題";
        answerForm.classList.toggle("hidden", isFinished);
        answerInput.value = "";
        showChat();
        setInterviewView(isFinished);
        if (isFinished) {
            await loadSummary(id, false);
        }
    } catch (error) {
        alert(`載入面試失敗：${error.message}`);
        if (error.message.includes("找不到面試 Session")) {
            if (readLastSession() === id) rememberLastSession(null);
            await refreshHistory();
        }
    } finally {
        setBusy(false);
    }
}

async function deleteSession(id) {
    if (busy) return;
    if (!window.confirm("確定刪除這場面試及全部問答紀錄？這個操作無法復原。")) return;
    setBusy(true);
    try {
        await apiRequest(`/api/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
        if (readLastSession() === id) rememberLastSession(null);
        if (sessionId === id) {
            sessionId = null;
            messages.replaceChildren();
            showSetup();
        }
        await refreshHistory();
    } catch (error) {
        alert(`刪除失敗：${error.message}`);
    } finally {
        setBusy(false);
    }
}

startForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    const background = document.getElementById("background").value.trim();
    const file = document.getElementById("resume-file").files[0];
    if (!background && !file) return alert("請輸入個人背景或上傳文件");
    if (file && file.size > 10 * 1024 * 1024) return alert("文件不可超過 10 MB");

    const formData = new FormData();
    formData.append("interview_type", document.getElementById("interview-type").value);
    formData.append("difficulty", document.getElementById("difficulty").value);
    formData.append("background", background);
    formData.append("max_topics", "3"); // 保留原本設定，之後可再做題數選單。
    if (file) formData.append("file", file);

    setBusy(true);
    startBtn.textContent = "正在解析文件並產生問題...";
    try {
        const result = await postAPI("/api/start", formData);
        sessionId = result.session_id;
        rememberLastSession(sessionId);
        messages.replaceChildren();
        answerInput.value = "";
        answerForm.classList.remove("hidden");
        topic.textContent = result.topic;
        addMessage(result.question, "ai");
        showChat();
        setInterviewView(false);
        if (result.document) {
            statusText.textContent = `已解析 ${result.document.filename}，共 ${result.document.chunk_count} 個片段；本題檢索到 ${result.retrieval.match_count} 個片段。`;
        } else {
            statusText.textContent = "已根據文字背景建立面試。";
        }
    } catch (error) {
        alert(error.message);
    } finally {
        startBtn.textContent = "開始面試";
        setBusy(false);
    }
});

answerForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    const answer = answerInput.value.trim();
    if (!sessionId || !answer) return;

    setBusy(true);
    statusText.textContent = "AI 面試官正在分析回答...";
    try {
        const result = await postAPI("/api/answer", { session_id: sessionId, answer });
        addMessage(answer, "user");
        answerInput.value = "";
        if (result.status === "finished") {
            addMessage("面試已完成，感謝你的回答！", "ai");
            statusText.textContent = "面試結束";
            topic.textContent = "已完成";
            setInterviewView(true);

            await loadSummary(sessionId, true);
        } else {
            topic.textContent = result.topic;
            addMessage(result.question, "ai");
            statusText.textContent = `決策：${result.decision}`;
        }
    } catch (error) {
        statusText.textContent = `${error.message}。如果請求逾時，請先點「重新載入進度」確認回答是否已儲存，再決定是否重新提交。`;
    } finally {
        setBusy(false);
    }
});

generateSummaryBtn.addEventListener("click", async () => {
    if (!sessionId) return;

    await loadSummary(sessionId, true);
});

// 重新整理歷史紀錄
refreshHistoryBtn?.addEventListener("click", refreshHistory);

// 重新載入當前面試
reloadSessionBtn?.addEventListener("click", () => {
    if (sessionId) loadSession(sessionId);
});

// 返回歷史清單或建立新面試
newInterviewBtn?.addEventListener("click", () => {
    if (busy) return;

    sessionId = null;
    rememberLastSession(null);
    messages.replaceChildren();
    summaryPanel.classList.add("hidden");

    showSetup();
    refreshHistory();
});

// 頁面初始化
(async function init() {
    console.log("Interview Agent 前端初始化開始");

    try {
        await refreshHistory();

        const previousId = readLastSession();

        if (previousId) {
            await loadSession(previousId);
        }

        console.log("Interview Agent 初始化完成");

    } catch (error) {
        console.error("初始化失敗：", error);

        if (historyStatus) {
            historyStatus.textContent =
                `初始化失敗：${error.message}`;
        }
    }
})();
