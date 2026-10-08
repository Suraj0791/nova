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
