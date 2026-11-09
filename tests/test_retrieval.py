
from src.tools.retrieval import retrieve_context


chunks = [
    {
        "doc_id": "project.pdf",
        "source": "page 1",
        "part": 1,
        "text": "本專題使用 RT-DETR 進行海浪偵測。"
    },
    {
        "doc_id": "project.pdf",
        "source": "page 2",
        "part": 1,
        "text": "利用 BoT-SORT 進行跨影格追蹤。"
    },
    {
        "doc_id": "project.pdf",
        "source": "page 3",
        "part": 1,
        "text": "使用 SVC 分類浪白與陽光反射。"
    }
]

result = retrieve_context(
    query="RT-DETR 海浪偵測",
    topic="專題技術原理",
    chunks=chunks,
    top_k=3
)

assert result["ok"] is True
assert result["data"]["count"] > 0
assert result["data"]["matches"][0]["source"] == "page 1"

print("=== Retrieval Tool ===")

for item in result["data"]["matches"]:
    print("來源：", item["source"])
    print("分數：", item["score"])
    print("內容：", item["text"])
    print()

print("檢索測試成功！")
