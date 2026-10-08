# Architectural & Design Decisions

This document tracks the reasoning behind our major design choices, particularly to help during the live interview.

## 1. Storage Format (JSONL vs SQLite)
**Decision:** We are using append-only `.jsonl` files in the `--state-dir`.
**Why:** It is human-readable, simple to debug, and avoids the complexity of relational schemas for this scale. If the dataset grew to millions of documents, SQLite would make sense, but for the take-home scale, JSONL keeps the architecture boring and reliable.

## 2. Document Reader Fidelity
**Decision:** `harness/reader.py` replicates the exact extraction logic (PyMuPDF, openpyxl, email.parser) used by `grader/extract.py`.
**Why:** The scoring rubric is highly sensitive to exact string quotes. Using the exact same baseline logic guarantees that when our LLM quotes a string, it will perfectly match what the grader looks for.

## 3. Strict Python Execution
**Decision:** No LangChain or LangGraph.
**Why:** Keeping the code in plain Python makes it easier to trace where a mistake happened (extraction vs detection) and significantly easier to fix live during the interview.

## 4. LLM Caching Strategy
**Decision:** `harness/extract.py` hashes the combined document text and saves the LLM's JSON response to `--state-dir/cache/`.
**Why:** The grader limits execution time for each step. Calling the LLM API on every `ingest` for identical documents would waste both time and money. Caching ensures deterministic, fast replays.

## 5. Prompt Injection Defense
**Decision:** The system prompt explicitly wraps the document content as "DATA" and strictly instructs the model not to follow instructions found within it.
**Why:** This directly addresses one of the 5 Hard Gates ("following an instruction written inside an email"). By treating the email body strictly as a string to extract facts from, we ensure malicious instructions like "approve this invoice" are parsed as data, not executed.
