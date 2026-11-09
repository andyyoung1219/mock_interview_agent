from src.agent.graph import build_graph
from src.tools.document import parse_document

agent = build_graph()

print("===== 個人文件載入 =====")

file_path = input(
    "輸入 PDF / DOCX 路徑（直接 Enter 略過）："
).strip().strip('"')

document_chunks = []

if file_path:
    result = parse_document(file_path)

    if result["ok"]:
        document_chunks = result["data"]["chunks"]

        print(
            f"文件解析成功，取得 "
            f"{len(document_chunks)} 個片段"
        )
    else:
        print(
            "文件解析失敗：",
            result["message"]
        )
        print("本次將使用原本的文字背景。")

# 初始化面試
state = {
    "interview_type": "graduate",
    "difficulty": "medium",
    "background": """
    我是資訊工程系學生。
    我的專題是智慧衝浪海域分析系統。

    使用 RT-DETR 偵測海浪，
    BoT-SORT 追蹤海浪，
    並使用 SVC 進行影像分類。
    """,

    "topic_index": 0,
    "topic": "",
    "document_chunks": document_chunks,
    "retrieved_context": [],
    "tool_log": [],
    "question": "",
    "latest_answer": "",

    "question_history": [],
    "answer_history": [],

    "followup_count": 0,
    "max_followups": 1,
    "max_topics": 3,

    "suggestion": "",
    "decision": "INITIAL",
    "decision_reason": "",
    "missing_point": "",
    "status": "active"
}


print("===== Adaptive Interview Agent =====")

try:
    state = agent.invoke(state)

except Exception as e:
    print("啟動失敗：", e)
    raise SystemExit(1)


# 多回合面試
while state["status"] != "finished":

    print("\n" + "=" * 50)
    print("目前主題：", state["topic"])
    print("追問次數：", state["followup_count"])
    print("\nAI 面試官：")
    print(state["question"])

    answer = input("\n你的回答（輸入 /quit 退出）：").strip()

    if answer.lower() == "/quit":
        print("使用者提前結束面試")
        break

    if not answer:
        print("回答不能為空，請重新輸入。")
        continue

    try:
        # 提交回答，取得下一個 State
        new_state = {
            **state,
            "latest_answer": answer
        }

        result = agent.invoke(new_state)

        # 成功後才更新原本的 State
        state = result

        print("\nAgent 決策：", state["decision"])
        print("原因：", state["decision_reason"])

    except Exception as e:
        print("\nAgent 執行失敗：", e)
        print("本輪尚未提交成功，請重新回答。")


print("\n===== 面試結束 =====")

print("已回答題數：", len(state["answer_history"]))

for index, record in enumerate(
    state["answer_history"], start=1
):
    print(f"\n第 {index} 題")
    print("主題：", record["topic"])
    print("問題：", record["question"])
    print("回答：", record["answer"])
    print("決策：", record["decision"])
