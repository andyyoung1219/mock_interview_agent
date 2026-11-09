
from pathlib import Path

import pymupdf
from docx import Document


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 20
CHUNK_SIZE = 1000


def split_text(text: str, size: int = CHUNK_SIZE):
    """將長文字切成多個片段。"""
    text = text.strip()

    return [
        text[i:i + size]
        for i in range(0, len(text), size)
    ]


def parse_document(file_path: str) -> dict:
    """
    解析 PDF / DOCX。

    Input:
        file_path: 文件路徑

    Output:
        {
            "ok": bool,
            "data": dict | None,
            "error_code": str | None,
            "message": str
        }
    """

    path = Path(file_path)

    # ===== 1. 檢查檔案 =====

    if not path.is_file():
        return {
            "ok": False,
            "data": None,
            "error_code": "FILE_NOT_FOUND",
            "message": "找不到指定的檔案"
        }

    if path.suffix.lower() not in [".pdf", ".docx"]:
        return {
            "ok": False,
            "data": None,
            "error_code": "UNSUPPORTED_FORMAT",
            "message": "只支援 PDF 和 DOCX"
        }

    if path.stat().st_size > MAX_FILE_SIZE:
        return {
            "ok": False,
            "data": None,
            "error_code": "FILE_TOO_LARGE",
            "message": "檔案不可超過 10 MB"
        }

    chunks = []
    doc_id = path.name

    try:

        # ===== 2. PDF 解析 =====

        if path.suffix.lower() == ".pdf":

            with pymupdf.open(str(path)) as pdf:

                if len(pdf) > MAX_PDF_PAGES:
                    return {
                        "ok": False,
                        "data": None,
                        "error_code": "TOO_MANY_PAGES",
                        "message": "PDF 不可超過 20 頁"
                    }

                for page_no, page in enumerate(pdf, start=1):

                    text = page.get_text("text")

                    for part_no, part in enumerate(
                        split_text(text), start=1
                    ):
                        chunks.append({
                            "doc_id": doc_id,
                            "source": f"page {page_no}",
                            "part": part_no,
                            "text": part
                        })

        # ===== 3. DOCX 解析 =====

        elif path.suffix.lower() == ".docx":

            document = Document(str(path))

            # 取得一般段落
            for para_no, paragraph in enumerate(
                document.paragraphs, start=1
            ):
                for part_no, part in enumerate(
                    split_text(paragraph.text), start=1
                ):
                    chunks.append({
                        "doc_id": doc_id,
                        "source": f"paragraph {para_no}",
                        "part": part_no,
                        "text": part
                    })

            # 取得表格內容
            for table_no, table in enumerate(
                document.tables, start=1
            ):
                for row_no, row in enumerate(
                    table.rows, start=1
                ):
                    row_text = " | ".join(
                        cell.text for cell in row.cells
                    )

                    for part_no, part in enumerate(
                        split_text(row_text), start=1
                    ):
                        chunks.append({
                            "doc_id": doc_id,
                            "source": (
                                f"table {table_no}, row {row_no}"
                            ),
                            "part": part_no,
                            "text": part
                        })

        # ===== 4. 檢查解析結果 =====

        if not chunks:
            return {
                "ok": False,
                "data": None,
                "error_code": "NO_TEXT",
                "message": (
                    "文件沒有可讀取的文字，"
                    "掃描 PDF 可能需要 OCR"
                )
            }

        return {
            "ok": True,
            "data": {
                "doc_id": doc_id,
                "chunk_count": len(chunks),
                "chunks": chunks
            },
            "error_code": None,
            "message": "文件解析成功"
        }

    except Exception as error:
        return {
            "ok": False,
            "data": None,
            "error_code": "PARSE_FAILED",
            "message": f"文件解析失敗：{type(error).__name__}"
        }
