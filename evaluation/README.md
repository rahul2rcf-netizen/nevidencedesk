# Evaluation dataset v1

`dataset/v1.json` contains 50 deliberately synthetic question cases against `sample_docs/policy-handbook.txt`: 40 answerable questions and 10 unanswerable questions. The fictional handbook is included in the repository and clearly labeled as demo data. It is not evidence about any real organization.

Run `python evaluation/run.py` from the repository root after installing backend dependencies. The script reports Recall@5, MRR, citation correctness, groundedness proxy, refusal quality, measured local latency, and model/API cost (zero for extractive mode; unknown for configured external providers). Results are written to `evaluation/results/latest.json`; reruns overwrite that report. Metrics are proxies and must not be read as a human-reviewed quality benchmark.
