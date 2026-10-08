from decimal import Decimal, ROUND_HALF_UP
from . import resolve

def money(amount: Decimal | str | float) -> Decimal:
    """Always use this for money to round to 2 decimal places using half-up."""
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def detect_overcharge(facts: list[dict], as_of: str) -> list[dict]:
    findings = []
    
    # 1. Get all invoice lines that are freight charges (not fuel or late fees yet)
    invoice_lines = [f for f in facts if f.get("type") == "invoice_line" and f.get("charge_type") in ("air_freight", "freight")]
    
    for line in invoice_lines:
        invoice_id = line.get("invoice_id", "unknown")
        awb = line.get("awb", "")
        lane = line.get("lane")
        qty = float(line.get("quantity", 0))
        billed_amount = money(line.get("amount", 0))
        
        # Get invoice date for fallback
        inv_meta = next((f for f in facts if f.get("type") == "invoice_meta" and f.get("invoice_id") == invoice_id), None)
        invoice_date = inv_meta.get("invoice_date", as_of) if inv_meta else as_of
        
        # 2. Determine pickup date
        pickup_date = resolve.get_pickup_date(awb, invoice_date, facts)
        
        # 3. Find correct rate
        active_rate_fact = resolve.get_active_rate(lane, qty, pickup_date, facts)
        if not active_rate_fact:
            # Missing contract or rate not found -> cannot_determine
            # We will handle missing docs in a later slice, for now skip.
            continue
            
        contract_rate = money(active_rate_fact.get("rate", 0))
        correct_freight = money(contract_rate * Decimal(str(qty)))
        
        # Calculate fuel (Simplified for now: assume 0 fuel or constant fuel if not extracted)
        # We will need fuel table extraction to be accurate.
        correct_fuel = money("0.00")
        correct_total = correct_freight + correct_fuel
        
        if billed_amount > correct_total:
            diff = billed_amount - correct_total
            
            # Format as a finding
            finding = {
                "id": f"overcharge:{invoice_id}:{awb}",
                "class": "overcharge",
                "key": {"invoice_id": invoice_id, "class": "overcharge"},
                "verdict": "finding",
                "amount_usd": str(diff),
                "action": "human_review", # Fallback, we'll set proper action in actions.py
                "confidence": 0.95,
                "evidence": [
                    {
                        "doc": active_rate_fact.get("doc_ref", ""),
                        "page": 1,
                        "quote": active_rate_fact.get("quote", "")
                    },
                    {
                        "doc": line.get("doc_ref", ""),
                        "page": 1,
                        "quote": line.get("quote", "")
                    }
                ]
            }
            findings.append(finding)
            
    return findings
