import hashlib
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from evidencedesk.config import Settings, get_settings
from evidencedesk.db import Database
from evidencedesk.generation.answer import answer
from evidencedesk.ingestion.extract import chunks, extract
from evidencedesk.retrieval.search import search
from evidencedesk.schemas import AnswerOut, AskRequest, DocumentOut, FeedbackRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("evidencedesk")


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    db = Database(cfg.data_dir / "evidencedesk.sqlite3")
    upload_dir = cfg.data_dir / "uploads"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        db.initialize()
        upload_dir.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(title="EvidenceDesk API", version="0.1.0", lifespan=lifespan)
    app.state.settings = cfg
    app.state.db = db
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        return {"status": "ok", "retrieval": cfg.retrieval_mode, "generator": cfg.llm_provider}

    @app.get("/api/documents", response_model=list[DocumentOut])
    def list_documents():
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [document_dict(row, cfg) for row in rows]

    @app.post("/api/documents", response_model=DocumentOut, status_code=201)
    async def upload(file: UploadFile = File(...)):
        filename = Path(file.filename or "").name
        ext = Path(filename).suffix.lower()
        if ext not in {".pdf", ".txt"}:
            raise HTTPException(415, "Only PDF and TXT files are supported")
        content = await file.read(cfg.max_upload_mb * 1024 * 1024 + 1)
        if not content:
            raise HTTPException(400, "The uploaded file is empty")
        if len(content) > cfg.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"File exceeds the {cfg.max_upload_mb} MB upload limit")
        kind = ext[1:]
        if kind == "pdf" and not content.startswith(b"%PDF-"):
            raise HTTPException(415, "The file extension says PDF but its content is not a PDF")
        if kind == "txt":
            try:
                content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise HTTPException(415, "TXT files must use UTF-8 encoding") from exc
        digest = hashlib.sha256(content).hexdigest()
        doc_id = str(uuid.uuid4())
        path = upload_dir / f"{doc_id}.{kind}"
        path.write_bytes(content)
        title = Path(filename).stem[:240] or "Untitled"
        now = datetime.now(UTC).isoformat()
        try:
            extracted = extract(path, kind)
            pieces = chunks(extracted.pages, cfg.chunk_size, cfg.chunk_overlap)
            if not pieces:
                raise ValueError("No extractable text found. This document may require OCR.")
            with db.connect() as conn:
                conn.execute("INSERT INTO documents(id,sha256,title,filename,file_type,size_bytes,status,page_count,chunk_count,ocr_pages,source_date,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (doc_id, digest, title, filename, kind, len(content), "indexed", len(extracted.pages), len(pieces), db.json(extracted.ocr_pages), extracted.source_date, now))
                conn.executemany("INSERT INTO chunks(id,document_id,page,section,text) VALUES(?,?,?,?,?)",
                    [(str(uuid.uuid4()), doc_id, p.page, p.section, p.text) for p in pieces])
        except Exception as exc:
            path.unlink(missing_ok=True)
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(409, "This document has already been uploaded") from exc
            log.exception("Ingestion failed for %s", filename)
            raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else "Document indexing failed") from exc
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        return document_dict(row, cfg)

    @app.delete("/api/documents/{doc_id}", status_code=204)
    def delete_document(doc_id: str):
        with db.connect() as conn:
            row = conn.execute("SELECT file_type FROM documents WHERE id=?", (doc_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Document not found")
            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        (upload_dir / f"{doc_id}.{row['file_type']}").unlink(missing_ok=True)

    @app.get("/api/documents/{doc_id}/pages/{page}")
    def preview_page(doc_id: str, page: int):
        with db.connect() as conn:
            row = conn.execute("SELECT title FROM documents WHERE id=?", (doc_id,)).fetchone()
            pieces = conn.execute("SELECT text FROM chunks WHERE document_id=? AND page=? ORDER BY rowid", (doc_id, page)).fetchall()
        if not row:
            raise HTTPException(404, "Document not found")
        return {"document_title": row["title"], "page": page,
                "text": " ".join(item["text"] for item in pieces)}

    @app.post("/api/ask", response_model=AnswerOut)
    def ask(request: AskRequest):
        started = time.perf_counter()
        with db.connect() as conn:
            rows = [dict(r) for r in conn.execute("SELECT c.*,d.title document_title,d.source_date FROM chunks c JOIN documents d ON d.id=c.document_id").fetchall()]
        results = search(request.question, rows, cfg, request.top_k)
        evidence = [item for item in results if item["score"] >= cfg.min_relevance]
        text, abstained = answer(request.question, evidence, cfg)
        citations = [{"document_id": r["document_id"], "document_title": r["document_title"],
                      "page": r["page"], "excerpt": r["text"][:700], "source_date": r.get("source_date"),
                      "outdated": is_outdated(r.get("source_date"), cfg)} for r in evidence[:5]] if not abstained else []
        warnings = answer_warnings(evidence, cfg) if not abstained else []
        if abstained and evidence and cfg.llm_provider == "openai-compatible":
            warnings.append("The configured answer provider failed or returned no answer. The response was withheld.")
        elapsed = (time.perf_counter() - started) * 1000
        answer_id = str(uuid.uuid4())
        with db.connect() as conn:
            conn.execute("INSERT INTO answers(id,question,answer,abstained,citations,latency_ms,created_at,warnings) VALUES(?,?,?,?,?,?,?,?)",
                         (answer_id, request.question, text, int(abstained), db.json(citations), elapsed, datetime.now(UTC).isoformat(), db.json(warnings)))
        return {"id": answer_id, "question": request.question, "answer": text, "abstained": abstained,
                "citations": citations, "latency_ms": round(elapsed, 2), "warnings": warnings}

    @app.get("/api/history")
    def history():
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM answers ORDER BY created_at DESC LIMIT 100").fetchall()
        return [{"id": r["id"], "question": r["question"], "answer": r["answer"],
                 "abstained": bool(r["abstained"]), "citations": json.loads(r["citations"]),
                 "latency_ms": r["latency_ms"], "warnings": json.loads(r["warnings"]),
                 "created_at": r["created_at"]} for r in rows]

    @app.post("/api/answers/{answer_id}/feedback", status_code=201)
    def feedback(answer_id: str, request: FeedbackRequest):
        with db.connect() as conn:
            if not conn.execute("SELECT 1 FROM answers WHERE id=?", (answer_id,)).fetchone():
                raise HTTPException(404, "Answer not found")
            conn.execute("INSERT INTO feedback(answer_id,rating,comment,created_at) VALUES(?,?,?,?)",
                         (answer_id, request.rating, request.comment, datetime.now(UTC).isoformat()))
        return {"status": "recorded"}

    return app


def is_outdated(source_date: str | None, cfg: Settings) -> bool:
    if not source_date:
        return False
    try:
        return date.fromisoformat(source_date) < date.today() - timedelta(days=cfg.outdated_after_days)
    except ValueError:
        return False


def document_dict(row, cfg: Settings):
    result = dict(row)
    result["ocr_pages"] = json.loads(result["ocr_pages"])
    result["outdated"] = is_outdated(result.get("source_date"), cfg)
    return result


def answer_warnings(evidence: list[dict], cfg: Settings) -> list[str]:
    warnings = []
    if any(is_outdated(item.get("source_date"), cfg) for item in evidence):
        warnings.append("At least one cited PDF has an old modification date. Confirm it is still current.")
    stop = {"the", "and", "for", "with", "from", "that", "this", "when", "what", "where", "which", "into", "must", "may", "are", "was"}
    for index, left in enumerate(evidence):
        left_terms = set(re.findall(r"[a-z]{4,}", left["text"].lower())) - stop
        left_values = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", left["text"]))
        for right in evidence[index + 1:]:
            right_terms = set(re.findall(r"[a-z]{4,}", right["text"].lower())) - stop
            right_values = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", right["text"]))
            if left["document_id"] != right["document_id"] and len(left_terms & right_terms) >= 3 and left_values and right_values and left_values != right_values:
                warnings.append("Potential conflict: similar passages from different documents contain different numeric values. Review both citations.")
                return warnings
    return warnings


app = create_app()
