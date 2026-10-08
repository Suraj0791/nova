from decimal import Decimal

MAX_AUTONOMOUS_INVOICE_TOTAL = Decimal("5000.00")

def set_finding_action(finding: dict, mode: str, invoice_total: Decimal) -> None:
    verdict = finding.get("verdict")
    finding_class = finding.get("class")
    
    # Internal actions are always safe
    if finding_class in ("expiry", "late_fee_risk", "cashback"):
        if finding_class == "expiry":
            finding["action"] = "internal:alert"
        elif finding_class == "late_fee_risk":
            finding["action"] = "internal:payment_reminder"
        elif finding_class == "cashback":
            finding["action"] = "internal:track_credit"
        return

    # Base action logic for findings
    if verdict == "conflict":
        base_action = "escalate"
    elif verdict == "cannot_determine":
        base_action = "request_document"
    elif verdict == "no_finding":
        finding["action"] = "none"
        return
    else:
        base_action = "dispute"

    # Now apply Gates
    if mode == "supervised":
        # Hard Gate: Supervised never sends outbound.
        if base_action == "escalate":
            finding["action"] = "escalate"
        else:
            finding["action"] = f"draft:{base_action}"
    else: # autonomous
        # Hard Gate: Autonomous only sends if ALL 4 conditions hold
        # 1. evidence complete (confidence > 0.8)
        evidence_complete = finding.get("confidence", 0.0) > 0.8 and len(finding.get("evidence", [])) > 0
        # 2. no conflict
        no_conflict = verdict != "conflict"
        # 3. invoice under $5k
        under_5k = invoice_total < MAX_AUTONOMOUS_INVOICE_TOTAL
        # 4. action reversible
        is_reversible = base_action in ("dispute", "request_document")
        
        if evidence_complete and no_conflict and under_5k and is_reversible:
            finding["action"] = f"execute:{base_action}"
        else:
            # If any condition fails, fallback safely
            if base_action == "escalate":
                finding["action"] = "escalate"
            else:
                finding["action"] = "human_review"
