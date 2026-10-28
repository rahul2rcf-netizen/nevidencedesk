from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidencedesk.config import Settings
from evidencedesk.api import answer_warnings, create_app, is_outdated
from evidencedesk.generation.answer import ABSTENTION, answer
from evidencedesk.ingestion.extract import ExtractedPage, chunks, extract
from evidencedesk.retrieval.search import search


def test_txt_extract_and_chunk_preserve_page_and_section(tmp_path: Path):
    source = tmp_path / "guide.txt"
    source.write_text("# Access\n" + "Employees must use multifactor authentication. " * 10)
    extracted = extract(source, "txt")
    pieces = chunks(extracted.pages, 200, 20)
    assert extracted.pages[0].page == 1
    assert pieces and all(p.page == 1 for p in pieces)
    assert pieces[0].section == "Access"


def test_search_ranks_matching_evidence():
    rows = [{"id": "1", "text": "Staff must submit expenses within thirty days."},
            {"id": "2", "text": "The office kitchen closes at five."}]
    cfg = Settings(embedding_provider="hash", retrieval_mode="bm25")
    assert search("expense submission deadline", rows, cfg, 1)[0]["id"] == "1"


def test_answer_abstains_without_evidence():
    result, abstained = answer("unknown", [], Settings(embedding_provider="hash"))
    assert result == ABSTENTION and abstained


@pytest.fixture
def client(tmp_path: Path):
    cfg = Settings(data_dir=tmp_path, embedding_provider="hash", retrieval_mode="bm25")
    with TestClient(create_app(cfg)) as test_client:
        yield test_client


def test_upload_ask_cite_history_feedback_and_delete(client: TestClient):
    payload = b"# Reimbursements\nEmployees may claim travel expenses within 30 days of the trip. " * 4
    uploaded = client.post("/api/documents", files={"file": ("policy.txt", payload, "text/plain")})
    assert uploaded.status_code == 201, uploaded.text
    doc = uploaded.json()
    assert doc["status"] == "indexed" and doc["chunk_count"] > 0
    answer_result = client.post("/api/ask", json={"question": "When claim travel expenses?"})
    assert answer_result.status_code == 200
    record = answer_result.json()
    assert not record["abstained"] and record["citations"][0]["document_id"] == doc["id"]
    assert record["citations"][0]["page"] == 1
    assert client.get("/api/history").json()[0]["id"] == record["id"]
    assert client.post(f"/api/answers/{record['id']}/feedback", json={"rating": "helpful"}).status_code == 201
    assert client.delete(f"/api/documents/{doc['id']}").status_code == 204


def test_rejects_wrong_type_duplicate_and_unanswerable(client: TestClient):
    assert client.post("/api/documents", files={"file": ("bad.exe", b"x", "application/octet-stream")}).status_code == 415
    payload = b"The library opens at nine in the morning. " * 5
    assert client.post("/api/documents", files={"file": ("hours.txt", payload)}).status_code == 201
    assert client.post("/api/documents", files={"file": ("hours-copy.txt", payload)}).status_code == 409
    result = client.post("/api/ask", json={"question": "What is the moon made of?"}).json()
    assert result["abstained"] and not result["citations"]


def test_rejects_fake_pdf(client: TestClient):
    response = client.post("/api/documents", files={"file": ("fake.pdf", b"plain text", "application/pdf")})
    assert response.status_code == 415


def test_flags_outdated_sources_and_possible_numeric_conflicts():
    cfg = Settings(embedding_provider="hash", outdated_after_days=365)
    assert is_outdated("2020-01-01", cfg)
    evidence = [
        {"document_id": "a", "source_date": None, "text": "The annual room limit allows 12 guests."},
        {"document_id": "b", "source_date": None, "text": "The annual room limit allows 20 guests."},
    ]
    warnings = answer_warnings(evidence, cfg)
    assert any("Potential conflict" in warning for warning in warnings)
