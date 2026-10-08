"""Your harness. The grader calls exactly these three commands, in a fresh process each time:

    python harness.py ingest <batch_dir> --state-dir <dir>
    python harness.py report --as-of YYYY-MM-DD [--mode supervised|autonomous] [--state-dir <dir>] > report.json
    python harness.py feedback <feedback.json> --state-dir <dir>

- ingest: read every .eml in <batch_dir> (attachments inside) and store what you learn under --state-dir. The process
  is restarted between batches, so everything you need later must be on disk.
- report: print one report.json (grader/schema/report.schema.json) to stdout. Only documents received on or before
  --as-of count. --mode defaults to supervised.
- feedback: take in a person's decisions on what you escalated (feedback.json) and let them change later reports.

The environment gives ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL. Keep the argument names as they are: grader/validate.py
checks them. Replace the NotImplementedError bodies with your code.
"""
from __future__ import annotations

import argparse
import sys

DEFAULT_STATE = ".state"


def ingest(batch_dir: str, state_dir: str) -> None:
    import os
    import uuid
    from . import reader
    from . import extract
    from . import store
    
    os.makedirs(state_dir, exist_ok=True)
    
    # Read all documents in the batch
    docs = reader.read_batch(batch_dir)
    print(f"Read {len(docs)} documents from {batch_dir}")
    
    all_facts = []
    for doc_ref, (pages, is_scan) in docs.items():
        if is_scan and not pages:
            print(f"Skipping {doc_ref}: image-only scan without text layer")
            continue
            
        extraction = extract.extract_facts(doc_ref, pages, state_dir)
        
        for fact in extraction.get("facts", []):
            fact["doc_ref"] = doc_ref
            fact["fact_id"] = str(uuid.uuid4())
            all_facts.append(fact)
            
    store.save_facts(state_dir, all_facts)
    print(f"Extracted and saved {len(all_facts)} facts")


def report(as_of: str, mode: str, state_dir: str) -> dict:
    import json
    from . import store
    from . import detectors
    from . import actions
    
    # 1. Load all facts
    facts = store.load_facts(state_dir)
    
    # 2. Run detectors
    findings = detectors.detect_overcharge(facts, as_of)
    findings.extend(detectors.detect_duplicate(facts, as_of))
    findings.extend(detectors.detect_waived(facts, as_of))
    
    late_findings, late_risks = detectors.detect_late_fees(facts, as_of)
    findings.extend(late_findings)
    
    cashback_risks, expiry_risks = detectors.calculate_cashback_and_expiry(facts, as_of)
    
    # 3. Process actions
    from decimal import Decimal
    invoice_lines = [f for f in facts if f.get("type") == "invoice_line"]
    invoice_totals = {}
    for line in invoice_lines:
        inv_id = line.get("invoice_id")
        amount = Decimal(str(line.get("amount", "0.00")))
        invoice_totals[inv_id] = invoice_totals.get(inv_id, Decimal("0.00")) + amount

    for finding in findings:
        inv_id = finding.get("key", {}).get("invoice_id")
        inv_total = invoice_totals.get(inv_id, Decimal("0.00"))
        actions.set_finding_action(finding, mode, inv_total)
        
    return {
        "as_of": as_of,
        "mode": mode,
        "findings": findings,
        "portfolio": {
            "cashback": cashback_risks,
            "expiry": expiry_risks,
            "late_fee_risk": late_risks
        }
    }


def feedback(feedback_file: str, state_dir: str) -> None:
    import json
    from pathlib import Path
    from . import store, extract
    
    ff = Path(feedback_file)
    if not ff.exists():
        return
        
    try:
        data = json.loads(ff.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Failed to read {feedback_file}")
        return
        
    if isinstance(data, dict):
        data = [data]
        
    store.save_feedback(state_dir, data)
    
    new_facts = []
    for item in data:
        explanation = item.get("explanation", "")
        if not explanation:
            continue
            
        facts = extract.extract_feedback_facts(explanation, item)
        new_facts.extend(facts)
        
    if new_facts:
        store.save_facts(state_dir, new_facts)
        print(f"Extracted and saved {len(new_facts)} new facts from feedback")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="harness.py", description="Freight invoice audit harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest", help="read one batch folder into the state dir")
    p.add_argument("batch_dir")
    p.add_argument("--state-dir", default=DEFAULT_STATE)
    p = sub.add_parser("report", help="print report.json for a date")
    p.add_argument("--as-of", required=True, help="YYYY-MM-DD; only documents received by then count")
    p.add_argument("--mode", choices=["supervised", "autonomous"], default="supervised")
    p.add_argument("--state-dir", default=DEFAULT_STATE)
    p = sub.add_parser("feedback", help="take in a person's decisions (feedback.json)")
    p.add_argument("feedback_file")
    p.add_argument("--state-dir", default=DEFAULT_STATE)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "ingest":
            ingest(a.batch_dir, a.state_dir)
        elif a.cmd == "report":
            import json
            json.dump(report(a.as_of, a.mode, a.state_dir), sys.stdout, indent=1)
            sys.stdout.write("\n")
        else:
            feedback(a.feedback_file, a.state_dir)
    except NotImplementedError as e:
        print(f"harness.py {a.cmd}: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
