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

def detect_duplicate(facts: list[dict], as_of: str) -> list[dict]:
    findings = []
    
    # 1. Type 2 Duplicate: Different invoice, same AWB + charge_type + amount
    invoice_lines = [f for f in facts if f.get("type") == "invoice_line"]
    seen_lines = {}
    
    for line in invoice_lines:
        awb = line.get("awb")
        charge_type = line.get("charge_type")
        amount = money(line.get("amount", 0))
        
        if not awb or not charge_type or amount == Decimal("0.00"):
            continue
            
        fingerprint = (awb, charge_type, str(amount))
        if fingerprint not in seen_lines:
            seen_lines[fingerprint] = []
        seen_lines[fingerprint].append(line)
        
    for fingerprint, lines in seen_lines.items():
        if len(lines) > 1:
            # Sort by invoice_date to flag the later invoice
            def get_inv_date(l):
                inv_id = l.get("invoice_id")
                meta = next((f for f in facts if f.get("type") == "invoice_meta" and f.get("invoice_id") == inv_id), None)
                return meta.get("invoice_date", as_of) if meta else as_of
                
            sorted_lines = sorted(lines, key=get_inv_date)
            original = sorted_lines[0]
            
            for dup_line in sorted_lines[1:]:
                invoice_id = dup_line.get("invoice_id", "unknown")
                findings.append({
                    "id": f"duplicate:{invoice_id}:{fingerprint[0]}:{fingerprint[1]}",
                    "class": "duplicate",
                    "key": {"invoice_id": invoice_id, "class": "duplicate"},
                    "verdict": "finding",
                    "amount_usd": fingerprint[2],
                    "action": "human_review",
                    "confidence": 0.95,
                    "evidence": [
                        {"doc": original.get("doc_ref", ""), "page": 1, "quote": original.get("quote", "")},
                        {"doc": dup_line.get("doc_ref", ""), "page": 1, "quote": dup_line.get("quote", "")}
                    ]
                })

    # 2. Type 1 Duplicate: Same invoice resent, already paid in AP register
    invoice_metas = [f for f in facts if f.get("type") == "invoice_meta"]
    ap_status = {f.get("invoice_id"): f for f in facts if f.get("type") == "ap_status"}
    
    seen_invoices = {}
    for meta in invoice_metas:
        inv_id = meta.get("invoice_id")
        if inv_id not in seen_invoices:
            seen_invoices[inv_id] = []
        seen_invoices[inv_id].append(meta)
        
    for inv_id, metas in seen_invoices.items():
        if len(metas) > 1:
            status = ap_status.get(inv_id)
            if status and status.get("status") in ("paid", "scheduled"):
                # Flag the full amount
                lines_for_inv = [l for l in invoice_lines if l.get("invoice_id") == inv_id]
                total_amount = sum((money(l.get("amount", 0)) for l in lines_for_inv), Decimal("0.00"))
                
                later_meta = metas[-1] # Simplistic, relies on ingest order
                findings.append({
                    "id": f"duplicate:{inv_id}:resent",
                    "class": "duplicate",
                    "key": {"invoice_id": inv_id, "class": "duplicate"},
                    "verdict": "finding",
                    "amount_usd": str(total_amount),
                    "action": "human_review",
                    "confidence": 0.90,
                    "evidence": [
                        {"doc": status.get("doc_ref", ""), "page": 1, "quote": status.get("quote", "")},
                        {"doc": later_meta.get("doc_ref", ""), "page": 1, "quote": later_meta.get("quote", "")}
                    ]
                })
                
    return findings

def detect_waived(facts: list[dict], as_of: str) -> list[dict]:
    findings = []
    
    invoice_lines = [f for f in facts if f.get("type") == "invoice_line"]
    waivers = [f for f in facts if f.get("type") == "waiver"]
    
    for waiver in waivers:
        sender = waiver.get("sender", "")
        
        # Hard Gate Defense: Check authority
        if not resolve.is_authorized(sender, "waivers", facts):
            continue
            
        waived_charge_type = waiver.get("waived_charge_type")
        exact_scope = waiver.get("exact_scope", "") # usually an AWB
        
        for line in invoice_lines:
            # Check scope (AWB match) and charge type match
            if line.get("awb") == exact_scope and line.get("charge_type") == waived_charge_type:
                amount = money(line.get("amount", 0))
                if amount > Decimal("0.00"):
                    invoice_id = line.get("invoice_id", "unknown")
                    findings.append({
                        "id": f"waived:{invoice_id}:{exact_scope}:{waived_charge_type}",
                        "class": "waived_but_billed",
                        "key": {"invoice_id": invoice_id, "class": "waived_but_billed"},
                        "verdict": "finding",
                        "amount_usd": str(amount),
                        "action": "human_review",
                        "confidence": 0.95,
                        "evidence": [
                            {"doc": waiver.get("doc_ref", ""), "page": 1, "quote": waiver.get("quote", "")},
                            {"doc": line.get("doc_ref", ""), "page": 1, "quote": line.get("quote", "")}
                        ]
                    })
                    
    return findings

def detect_late_fees(facts: list[dict], as_of: str) -> tuple[list[dict], list[dict]]:
    """Returns (findings, risk_portfolio)"""
    from datetime import datetime
    findings = []
    risk_portfolio = []
    
    invoice_lines = [f for f in facts if f.get("type") == "invoice_line"]
    ap_statuses = {f.get("invoice_id"): f for f in facts if f.get("type") == "ap_status"}
    
    # 1. Late fee not owed
    for line in invoice_lines:
        if line.get("charge_type") == "late_fee":
            invoice_id = line.get("invoice_id")
            final_due = resolve.get_due_date(invoice_id, facts)
            ap_entry = ap_statuses.get(invoice_id)
            
            if final_due and ap_entry:
                paid_date = ap_entry.get("paid_date")
                amount = money(line.get("amount", 0))
                
                is_late = False
                if paid_date and paid_date > final_due:
                    is_late = True
                elif not paid_date and as_of > final_due:
                    is_late = True
                    
                if not is_late and amount > Decimal("0.00"):
                    findings.append({
                        "id": f"late_not_owed:{invoice_id}",
                        "class": "late_fee_not_owed",
                        "key": {"invoice_id": invoice_id, "class": "late_fee_not_owed"},
                        "verdict": "finding",
                        "amount_usd": str(amount),
                        "action": "human_review",
                        "confidence": 0.95,
                        "evidence": [
                            {"doc": line.get("doc_ref", ""), "page": 1, "quote": line.get("quote", "")},
                            {"doc": ap_entry.get("doc_ref", ""), "page": 1, "quote": ap_entry.get("quote", "")}
                        ]
                    })

    # 2. Late fee risk
    as_of_dt = datetime.strptime(as_of, "%Y-%m-%d")
    for invoice_id, ap_entry in ap_statuses.items():
        if ap_entry.get("status") == "unpaid":
            final_due = resolve.get_due_date(invoice_id, facts)
            if final_due:
                due_dt = datetime.strptime(final_due, "%Y-%m-%d")
                if (due_dt - as_of_dt).days <= 3:
                    # Calculate 5% risk if we want, or just set to 0.00 as per simple schema
                    # Let's approximate total invoice amount for the risk
                    lines = [l for l in invoice_lines if l.get("invoice_id") == invoice_id]
                    total_inv = sum((money(l.get("amount", 0)) for l in lines), Decimal("0.00"))
                    risk_amount = money(total_inv * Decimal("0.05"))
                    
                    # Ensure evidence includes the invoice/ap status and extension if any
                    risk_portfolio.append({
                        "id": f"risk:{invoice_id}",
                        "class": "late_fee_risk",
                        "key": {"invoice_id": invoice_id, "class": "late_fee_risk"},
                        "verdict": "finding",
                        "amount_usd": str(risk_amount),
                        "action": "internal:payment_reminder",
                        "confidence": 0.90,
                        "evidence": [
                            {"doc": ap_entry.get("doc_ref", ""), "page": 1, "quote": ap_entry.get("quote", "")}
                        ]
                    })
                    
    return findings, risk_portfolio
