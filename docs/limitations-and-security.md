# Privacy, security, and design trade-offs

## Data handling

Uploads are restricted to `.pdf` and `.txt`, checked against content signatures/UTF-8, limited by `ED_MAX_UPLOAD_MB`, and saved to an application-owned directory under a random UUID filename. SHA-256 prevents indexing byte-identical duplicates. SQLite stores filenames, titles, status, extraction page counts, OCR-needed pages, chunks, question history, and feedback. Delete removes the stored upload and its document/chunk metadata; answer history is retained and may contain cited excerpts.

The default extractive path runs locally. Sentence Transformer weights may be fetched when first used if they are not already cached; embeddings and passage text are processed in the local process. With `ED_LLM_PROVIDER=openai-compatible`, retrieved excerpts and the question are sent to the configured endpoint. That can be a hosted API or a local server. Configure that explicitly and assess data handling before use. API keys belong only in environment variables or an untracked `.env` file.

No application-level encryption, user authentication, tenant boundary, malware scanning, antivirus integration, network access control, or retention policy is included. Protect the data directory and SQLite volume with host permissions and backups. Do not publish the unauthenticated service to the public internet.

## Uploaded-file and prompt-injection risks

File extension and PDF signature checks are not malware scanning. A file size limit does not fully prevent parser resource exhaustion from adversarial PDFs. Keep PyMuPDF patched, use a low-privilege container, consider CPU/memory/page-count limits and malware scanning before production, and avoid exposing raw upload storage through a static web server. The backend does not execute macros or embedded content.

Uploaded text is untrusted. The generation prompt instructs the model to treat passages as data rather than instructions and to answer from evidence only. Prompt injection can still influence a model, so citations and instructions are not a security boundary. The extractive default avoids model instruction following but only selects sentences and may return incomplete context. Review cited passages for consequential decisions.

## Retrieval and answer trade-offs

BM25 provides an offline lexical fallback. Semantic search uses normalized Sentence Transformer embeddings and FAISS when the optional packages and model weights are present; otherwise it falls back to lexical scores. The in-memory FAISS index is rebuilt per question, trading implementation simplicity for latency and scalability. Hybrid weights and the abstention threshold need calibration against a representative collection.

Chunking is page aware and uses fixed character windows. It can split tables, headings, or sentence boundaries. Scanned pages are identified heuristically by low extracted character count; OCR is not run. PDF modification dates older than a configurable threshold are flagged, but TXT source dates and document authority are unknown. A heuristic flags cross-document passages with overlapping vocabulary and different numeric values; it misses many conflicts and can produce false positives. It does not resolve which source is authoritative.

## Benchmark scope

The v1 test corpus is one fictional handbook with 40 answerable and 10 unanswerable questions. Recall and MRR require exact supporting-sentence containment in one of the top 5 chunks. Citation correctness checks that the retrieved evidence corresponds to the labeled document/page; groundedness checks whether the baseline answer contains the labeled sentence. Refusal quality is binary decision accuracy over answerable and unanswerable cases. These automated proxies can overstate real quality and do not measure semantic correctness, nuanced citation support, or user satisfaction. Latency is from the current local execution environment. Zero provider cost only means no hosted model call in extractive mode.

## Deliberate implementation choices

- SQLite keeps local metadata/history simple for a single-user portfolio demo.
- Upload indexing is synchronous so the API can return a definitive indexed status without a worker dependency.
- The LLM interface is OpenAI-compatible to support hosted APIs and local compatible endpoints with one configuration surface.
- No real-world documents or private data are bundled; the included corpus is explicitly labeled synthetic.
