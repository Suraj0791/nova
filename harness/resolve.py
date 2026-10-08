from datetime import datetime

def get_pickup_date(awb: str, invoice_date: str, facts: list[dict]) -> str:
    """
    Priority: 1. Tracking event (PICKED_UP) > 2. Email confirmation > 3. AWB date > 4. Invoice Date
    """
    tracking_events = [f for f in facts if f.get("type") == "tracking_event" and f.get("awb") == awb]
    for t in tracking_events:
        if t.get("event") == "PICKED_UP":
            return t.get("date")
            
    # For now, if no tracking event, fallback to invoice date.
    return invoice_date

def get_active_rate(lane: str, quantity: float, pickup_date: str, facts: list[dict]) -> dict | None:
    """Find the active contract rate for the given lane, quantity, and date."""
    rates = [f for f in facts if f.get("type") == "contract_rate" and f.get("lane") == lane]
    
    best_rate = None
    for r in rates:
        ef_from = r.get("effective_from")
        ef_to = r.get("effective_to")
        
        # Check date validity
        if ef_from and pickup_date < ef_from:
            continue
        if ef_to and pickup_date > ef_to:
            continue
            
        # Check weight band (e.g., "100-299.5" or "500+")
        band = r.get("weight_band", "")
        if "-" in band:
            low, high = band.split("-")
            if float(low) <= quantity < float(high):
                best_rate = r
                break
        elif "+" in band:
            low = band.replace("+", "")
            if quantity >= float(low):
                best_rate = r
                break
        elif not band:
            best_rate = r
            break
            
    return best_rate

def is_authorized(sender: str, category: str, facts: list[dict]) -> bool:
    """Checks if sender has authority for the given category via Schedule 1."""
    if not sender:
        return False
        
    if sender == "human_reviewer":
        return True
        
    sched1 = [f for f in facts if f.get("type") == "schedule_1"]
    for entry in sched1:
        # Simple substring match (e.g., "Elspeth Iyengar" in "Elspeth Iyengar <e.iyengar@qmp.com>")
        person = entry.get("person", "")
        if person and person.lower() in sender.lower():
            if category in entry.get("categories", []):
                return True
    return False

def get_due_date(invoice_id: str, facts: list[dict]) -> str | None:
    """Calculate the final due date considering the AP register and any authorized extensions."""
    ap_entry = next((f for f in facts if f.get("type") == "ap_status" and f.get("invoice_id") == invoice_id), None)
    if not ap_entry:
        return None
        
    base_due = ap_entry.get("due_date")
    if not base_due:
        return None
        
    extensions = [f for f in facts if f.get("type") == "extension" and f.get("invoice_id") == invoice_id]
    
    final_due = base_due
    for ext in extensions:
        sender = ext.get("sender", "")
        # Hard Gate Defense: Check authority for extensions
        if is_authorized(sender, "extensions", facts):
            new_due = ext.get("new_due_date")
            if new_due and new_due > final_due:
                final_due = new_due
                
    return final_due
