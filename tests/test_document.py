
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf
from docx import Document

from src.tools.document import parse_document


with TemporaryDirectory() as temp_dir:

    folder = Path(temp_dir)

    # ===== 建立測試 DOCX =====

    docx_path = folder / "test_resume.docx"

    word = Document()

    word.add_heading("測試專題履歷", level=1)

    word.add_paragraph(
        "我的專題使用 RT-DETR 進行海浪偵測。"
    )

    word.add_paragraph(
        "並且使用 BoT-SORT 進行跨影格追蹤。"
    )

    word.add_paragraph(
        "利用 SVC 進行浪白影像分類。"
    )

    word.save(docx_path)

    # ===== 建立測試 PDF =====

    pdf_path = folder / "test_project.pdf"

    pdf = pymupdf.open()
    page = pdf.new_page()

    page.insert_text(
        (72, 72),
        "RT-DETR wave detection and tracking"
    )

    pdf.save(str(pdf_path))
    pdf.close()

    # ===== 測試 DOCX =====

    print("=== DOCX Test ===")

    result = parse_document(str(docx_path))

    assert result["ok"] is True

    print("Status:", result["ok"])
    print("Chunks:", result["data"]["chunk_count"])

    for chunk in result["data"]["chunks"]:
        print(chunk["source"], chunk["text"])

    # ===== 測試 PDF =====

    print("\n=== PDF Test ===")

    result = parse_document(str(pdf_path))

    assert result["ok"] is True

    print("Status:", result["ok"])
    print("Chunks:", result["data"]["chunk_count"])

    for chunk in result["data"]["chunks"]:
        print(chunk["source"], chunk["text"])

    # ===== 測試不存在的檔案 =====

    print("\n=== Failure Test ===")

    result = parse_document(
        str(folder / "missing.pdf")
    )

    assert result["ok"] is False

    print("Status:", result["ok"])
    print("Error:", result["error_code"])

print("\n所有測試完成")
