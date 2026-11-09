
import re


def tokenize(text: str) -> set[str]:
    """將文字轉換成關鍵詞集合。"""

    text = text.lower()

    # 英文與技術詞，例如 RT-DETR、SVC
    english = re.findall(
        r"[a-z0-9]+(?:[-_][a-z0-9]+)*",
        text
    )

    # 中文連續字串
    chinese = re.findall(
        r"[\u4e00-\u9fff]+",
        text
    )

    tokens = set(english)

    # 中文使用 bigram
    for phrase in chinese:
        if len(phrase) == 1:
            tokens.add(phrase)
        else:
            for i in range(len(phrase) - 1):
                tokens.add(phrase[i:i + 2])

    return tokens


def retrieve_context(
    query: str,
    topic: str,
    chunks: list[dict],
    top_k: int = 3
) -> dict:
    """
    從文件片段中檢索相關資訊。

    Args:
        query: 搜尋文字
        topic: 面試主題
        chunks: parse_document() 產生的片段
        top_k: 最多回傳幾筆

    Returns:
        結構化檢索結果
    """

    if not isinstance(chunks, list):
        return {
            "ok": False,
            "data": None,
            "error_code": "INVALID_CHUNKS",
            "message": "文件片段格式不正確"
        }

    if not query.strip():
        return {
            "ok": False,
            "data": None,
            "error_code": "EMPTY_QUERY",
            "message": "搜尋文字不可為空"
        }

    query_tokens = tokenize(query)

    scored_chunks = []

    for chunk in chunks:
        text = chunk.get("text", "")

        if not isinstance(text, str) or not text.strip():
            continue

        chunk_tokens = tokenize(text)

        # 計算重疊的詞彙
        overlap = query_tokens & chunk_tokens

        # 英文技術詞給予較高權重
        score = sum(
            3 if re.search(r"[a-z0-9]", token) else 1
            for token in overlap
        )

        if score > 0:
            scored_chunks.append({
                "doc_id": chunk.get("doc_id", ""),
                "source": chunk.get("source", ""),
                "part": chunk.get("part", 1),
                "text": text,
                "score": score
            })

    scored_chunks.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    matches = scored_chunks[:max(1, min(top_k, 5))]

    return {
        "ok": True,
        "data": {
            "topic": topic,
            "query": query,
            "count": len(matches),
            "matches": matches
        },
        "error_code": None,
        "message": (
            "檢索成功" if matches
            else "沒有找到相關文件片段"
        )
    }
