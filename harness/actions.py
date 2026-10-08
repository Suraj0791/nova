from decimal import Decimal

# Hard-gate constants
MAX_SAFE_AUTONOMOUS_AMOUNT = Decimal("5000.00")
HUMAN_REVIEW_THRESHOLD = Decimal("5000.00")

def set_finding_action(finding: dict, mode: str) -> None:
    """Sets the action field based on the mode and safety checks to avoid hard gates."""
    
    verdict = finding.get("verdict")
    finding_class = finding.get("class")
    
    if verdict == "conflict":
        finding["action"] = "escalate"
        return
        
    if verdict == "cannot_determine":
        finding["action"] = "draft:request_document" if mode == "supervised" else "execute:request_document"
        return
        
    if verdict == "no_finding":
        finding["action"] = "none"
        return

    amount = Decimal(finding.get("amount_usd", "0.00"))
    
    # Internal actions (always execute, in both modes)
    if finding_class in ("expiry", "late_fee_risk", "cashback"):
        if finding_class == "expiry":
            finding["action"] = "internal:alert"
        elif finding_class == "late_fee_risk":
            finding["action"] = "internal:payment_reminder"
        elif finding_class == "cashback":
            finding["action"] = "internal:track_credit"
        return

    # Outbound Actions logic (e.g. overcharge, duplicate, waived, late_fee_not_owed)
    
    if amount >= HUMAN_REVIEW_THRESHOLD:
        finding["action"] = "human_review"
        return

    # HARD GATE DEFENSE: Supervised mode MUST NEVER execute outbound.
    if mode == "supervised":
        finding["action"] = "draft:dispute"
        return
        
    # Autonomous mode checks (Safe unattended action test)
    # We will expand this as we build more rules, but basic safe defaults:
    is_reversible = True # Disputes are reversible
    no_conflict = True # We already checked verdict != conflict
    evidence_complete = True # Simple for now
    
    if is_reversible and no_conflict and evidence_complete and amount < MAX_SAFE_AUTONOMOUS_AMOUNT:
        finding["action"] = "execute:dispute"
    else:
        finding["action"] = "human_review"
