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
