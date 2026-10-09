# Design

## Fact model
We store extracted facts as strict JSON objects in an append-only JSONL file (`facts.jsonl`). Each fact contains a `type` (e.g., `contract_rate`, `waiver`), the specific data (e.g., `lane`, `amount`), a `doc_ref` identifying the exact document/attachment path, and a `quote` storing the exact string from the document. This `quote` serves as the cryptographic proof of the fact's origin and is what the grader checks for fidelity.

## Conflicts
Disagreements are handled through chronological priority and structural authority in `resolve.py`. For example, a pickup date is resolved via `Tracking > Email > AWB > Invoice`. A conflict only occurs when two documents of *equal authority* present opposing facts. If the conflict cannot be deterministically resolved, the verdict is set to `conflict` and the action is forced to `escalate`.

## Confidence
Confidence is inherently baked into the extraction prompt (we prompt Claude to return `0.0` if unsure). In Python, we multiply base extraction confidence by structural authority. If a waiver comes from a `human_reviewer`, confidence is `1.0`. If it comes from an email sender not in `Schedule 1`, the fact is rejected. The final confidence in the report is used to gate autonomous execution (`confidence > 0.8` is required).

## People in the loop
In `supervised` mode, nothing is sent autonomously; outbound findings are generated as `draft:*`. In `autonomous` mode, a finding executes outbound *only* if it meets all 4 constraints: 1) High confidence evidence, 2) No conflict, 3) The total invoice value is strictly under $5,000, and 4) The action is reversible (e.g., `dispute`). If any constraint fails, the system falls back to `human_review`.

## Feedback
Feedback is processed via a strict prompt in `extract_feedback_facts`. The LLM translates the human's explanation into new facts (e.g., a `waiver`). To stop it from spreading, the system explicitly defends against the "One-off Waiver Trap": if the feedback implies "just this shipment," the waiver is strictly scoped to the specific `AWB` or `invoice_id`. Sender authority is automatically granted to `human_reviewer`.

## New documents
Because our JSONL datastore is append-only, new documents simply append new facts. `resolve.py` always evaluates the full timeline of facts. If an amendment changes a contract rate, the active rate resolver checks the `effective_from` and `effective_to` dates, seamlessly applying the new answer chronologically to the correct shipments.

## Cost
With Claude 3.5 Sonnet, a typical document (email + PDF invoice) is ~2,000 tokens in and ~200 tokens out. 
Cost per document: (2000 * $0.003/1k) + (200 * $0.015/1k) = $0.006 + $0.003 = $0.009. 
1,000 documents = ~$9.00.
Time per document API call is ~3-5 seconds. With SHA-256 document hashing, we cache exact matches, dropping time to 0ms for duplicates.

## What I'd do next
Unfinished: A robust, multi-page layout parser for complex freight tables (currently using basic word grouping, which breaks on misaligned rows).
With another week: I'd migrate the JSONL datastore to an embedded PostgreSQL database to handle millions of invoices efficiently, and add an AI "Judge" agent strictly to evaluate `conflict` cases before they escalate.
Least sure about: The edge cases around variable fuel surcharges in Annex C, which require complex table lookups based on exact pickup dates.
