"""Reproducible retrieval and answer evaluation over the labeled synthetic dataset."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from evidencedesk.config import Settings  # noqa: E402
from evidencedesk.generation.answer import answer  # noqa: E402
from evidencedesk.ingestion.extract import ExtractedPage, chunks  # noqa: E402
from evidencedesk.retrieval.search import BM25_IMPLEMENTATION, search  # noqa: E402


def main():
    dataset = json.loads((ROOT / "evaluation/dataset/v1.json").read_text(encoding="utf-8"))
    source = ROOT / "sample_docs/policy-handbook.txt"
    text = source.read_text(encoding="utf-8")
    rows = [{"id": str(i), "document_id": "northstar-demo", "document_title": "Northstar Community Center Policy Handbook — SYNTHETIC DEMO", "page": piece.page, "text": piece.text} for i, piece in enumerate(chunks([ExtractedPage(1, text)], 900, 120))]
    settings = Settings(embedding_provider="hash", retrieval_mode="bm25", min_relevance=0.40)
    recall, reciprocal, citations, grounded, refusals, latencies = [], [], [], [], [], []
    for item in dataset["questions"]:
        start = time.perf_counter()
        found = search(item["question"], rows, settings, 5)
        response, abstained = answer(item["question"], found, settings)
        latencies.append((time.perf_counter() - start) * 1000)
        relevant = [i for i, row in enumerate(found, 1) if row["page"] in item["supporting_pages"] and (not item["answerable"] or (row["document_id"] == item["supporting_document_id"] and item["evidence"].lower() in row["text"].lower()))]
        if item["answerable"]:
            recall.append(float(bool(relevant)))
            reciprocal.append(1 / relevant[0] if relevant else 0.0)
        citations.append(float((not item["answerable"] and abstained) or (item["answerable"] and not abstained and bool(relevant))))
        grounded.append(float(not abstained and item["evidence"].lower() in response.lower()) if item["answerable"] else float(abstained))
        refusals.append(float(abstained) if not item["answerable"] else float(not abstained))
    count = len(dataset["questions"])
    report = {"dataset_version": dataset["version"], "label": dataset["label"], "cases": count,
              "answerable_cases": sum(x["answerable"] for x in dataset["questions"]),
              "unanswerable_cases": sum(not x["answerable"] for x in dataset["questions"]),
              "retrieval": {"recall_at_5": sum(recall) / len(recall), "mrr": sum(reciprocal) / len(reciprocal)},
              "answer": {"citation_correctness_proxy": sum(citations) / count, "groundedness_proxy": sum(grounded) / count,
                         "refusal_quality": sum(refusals) / count},
              "latency_ms": {"mean": sum(latencies) / count, "p95": sorted(latencies)[int(.95 * (count - 1))]},
              "model_api_cost_usd": 0.0 if settings.llm_provider == "extractive" else None,
              "retrieval_implementation": BM25_IMPLEMENTATION,
              "method": "Local BM25 and extractive baseline; answerable retrieval relevance requires exact supporting-sentence containment in a retrieved chunk. Citation and groundedness use that labeled evidence proxy; refusal quality is binary decision accuracy. One synthetic handbook, not human adjudication."}
    result_path = ROOT / "evaluation/results/latest.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2)
    result_path.write_text(encoded, encoding="utf-8")
    (result_path.parent / "v1.json").write_text(encoded, encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
