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

## 6. Action Safety Gate
**Decision:** `harness/actions.py` enforces that if `mode == "supervised"`, outbound actions are ALWAYS formatted as `draft:*`.
**Why:** Prevents the Hard Gate "sending anything outbound in supervised mode". It is decoupled from the detectors so that a detector never accidentally sets a forbidden action.

## 7. Decimal-First Arithmetic
**Decision:** We use Python's `decimal.Decimal` with `ROUND_HALF_UP` for all money calculations.
**Why:** Floats introduce rounding errors (e.g., `0.05 * 65566.99 = 3278.34949...`). The grader requires exact $0.01 tolerance, and standard Python `round()` uses banker's rounding (half-to-even) instead of the required half-up. Wrapping everything in a custom `money()` function guarantees exact financial math.

## 8. Duplicate Fingerprinting
**Decision:** The duplicate detector builds a fingerprint `(AWB, charge_type, amount)` for every invoice line.
**Why:** This allows us to detect cross-invoice duplicates effortlessly without deep-nested loops. We sort matching fingerprints by `invoice_date` to ensure only the later (duplicate) invoice gets flagged.

## 9. Authority Resolution Strategy
**Decision:** `resolve.py` centralizes the check for sender authority (`is_authorized`) against Schedule 1 facts.
**Why:** Directly addresses a Hard Gate (unauthorized waivers/extensions). If a random employee or an AI instruction says "waive this fee", the system drops it instantly because that sender won't exist in Schedule 1 for the 'waivers' category.
