from dataclasses import dataclass
from pathlib import Path

import fitz
import re


@dataclass
class ExtractedPage:
    page: int
    text: str
    section: str | None = None


@dataclass
class Extraction:
    pages: list[ExtractedPage]
    ocr_pages: list[int]
    source_date: str | None = None


def extract(path: Path, file_type: str) -> Extraction:
    if file_type == "txt":
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        return Extraction([ExtractedPage(1, text)], [])
    try:
        doc = fitz.open(path)
        if doc.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported")
        pages: list[ExtractedPage] = []
        ocr: list[int] = []
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if len(text) < 20:
                ocr.append(index)
            headings = []
            sizes = []
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        value = span.get("text", "").strip()
                        size = span.get("size", 0)
                        if value:
                            sizes.append(size)
                            headings.append((value, size))
            largest = max(sizes, default=0)
            heading = next((value for value, size in headings if size >= max(13, largest - 0.2) and len(value) < 120), None)
            pages.append(ExtractedPage(index, text, heading))
        raw_date = (doc.metadata or {}).get("modDate", "")
        match = re.match(r"D:(\d{4})(\d{2})?(\d{2})?", raw_date)
        source_date = f"{match[1]}-{match[2] or '01'}-{match[3] or '01'}" if match else None
        return Extraction(pages, ocr, source_date)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise ValueError("Could not read this PDF; verify it is a valid, unencrypted PDF") from exc


def chunks(pages: list[ExtractedPage], size: int, overlap: int) -> list[ExtractedPage]:
    result: list[ExtractedPage] = []
    step = size - overlap
    for page in pages:
        text = " ".join(page.text.split())
        if not text:
            continue
        headings = [line.strip() for line in page.text.splitlines() if line.strip().startswith("#")]
        section = headings[-1].lstrip("# ") if headings else page.section
        for start in range(0, len(text), step):
            body = text[start : start + size].strip()
            if body:
                result.append(ExtractedPage(page.page, body, section))
    return result
