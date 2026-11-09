
let sessionId = null;

const startForm = document.getElementById("start-form");
const answerForm = document.getElementById("answer-form");
const chatPanel = document.getElementById("chat-panel");
const setupPanel = document.getElementById("setup-panel");
const messages = document.getElementById("messages");
const topic = document.getElementById("topic");
const statusText = document.getElementById("status");

const startBtn = document.getElementById("start-btn");
const sendBtn = document.getElementById("send-btn");

// 建立聊天訊息
function addMessage(text, role) {
    const div = document.createElement("div");

    div.className = `message ${role}`;
    div.textContent = text;

    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

// 共用 API 呼叫

async function postAPI(url, data) {
    const isFormData = data instanceof FormData;

    const options = {
        method: "POST",
        body: isFormData
            ? data
            : JSON.stringify(data),
    };

    // JSON 才自行設定 Content-Type
    // FormData 由瀏覽器自動設定 multipart boundary
    if (!isFormData) {
        options.headers = {
            "Content-Type": "application/json"
        };
    }

    const response = await fetch(url, options);

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            typeof result.detail === "string"
                ? result.detail
                : "伺服器發生錯誤"
        );
    }

    return result;
}


// 開始面試

startForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const background = document
        .getElementById("background")
        .value.trim();

    const fileInput = document
        .getElementById("resume-file");

    const file = fileInput.files[0];

    // 至少提供文字或文件
    if (!background && !file) {
        alert("請輸入個人背景或上傳文件");
        return;
    }

    // 前端先檢查檔案大小
    if (file && file.size > 10 * 1024 * 1024) {
        alert("文件不可超過 10 MB");
        return;
    }

    // 建立 multipart/form-data
    const formData = new FormData();

    formData.append(
        "interview_type",
        document.getElementById("interview-type").value
    );

    formData.append(
        "difficulty",
        document.getElementById("difficulty").value
    );

    formData.append("background", background);
    formData.append("max_topics", "3");

    if (file) {
        formData.append("file", file);
    }

    startBtn.disabled = true;
    startBtn.textContent = "正在解析文件並產生問題...";

    try {
        const result = await postAPI(
            "/api/start",
            formData
        );

        sessionId = result.session_id;

        setupPanel.classList.add("hidden");
        chatPanel.classList.remove("hidden");

        topic.textContent = result.topic;

        // 顯示第一道面試問題
        addMessage(result.question, "ai");

        // 顯示文件解析與檢索狀態
        if (result.document) {
            statusText.textContent =
                `已解析 ${result.document.filename}，` +
                `共 ${result.document.chunk_count} 個片段；` +
                `本題檢索到 ${result.retrieval.match_count} 個片段。`;
        } else {
            statusText.textContent =
                "已根據文字背景建立面試。";
        }

    } catch (error) {
        alert(error.message);

    } finally {
        startBtn.disabled = false;
        startBtn.textContent = "開始面試";
    }
});


// 提交回答
answerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const input = document.getElementById("answer");
    const answer = input.value.trim();

    if (!sessionId || !answer) return;

    sendBtn.disabled = true;
    input.disabled = true;
    statusText.textContent = "AI 面試官正在分析回答...";

    try {
        const result = await postAPI("/api/answer", {
            session_id: sessionId,
            answer: answer
        });

        addMessage(answer, "user");
        input.value = "";

        if (result.status === "finished") {
            addMessage("面試已完成，感謝你的回答！", "ai");
            statusText.textContent = "面試結束";
            answerForm.classList.add("hidden");
        } else {
            topic.textContent = result.topic;
            addMessage(result.question, "ai");
            statusText.textContent =
                `決策：${result.decision}`;
        }

    } catch (error) {
        statusText.textContent = error.message;

    } finally {
        if (!answerForm.classList.contains("hidden")) {
            sendBtn.disabled = false;
            input.disabled = false;
        }
    }
});
