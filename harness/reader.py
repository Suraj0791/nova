import io
import re
from datetime import date, datetime
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

SEP = " | "

def norm(s: str) -> str:
    return " ".join(s.split())

# ---- PDF --------------------------------------------------------------------------------------------------------------
def _reading_order(page) -> str:
    words = page.get_text("words")
    words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines: list[list] = []
    for w in words:
        mid = (w[1] + w[3]) / 2
        if lines and abs(lines[-1][0] - mid) <= 2.5:
            lines[-1][1].append(w)
        else:
            lines.append([mid, [w]])
    return "\n".join(" ".join(x[4] for x in sorted(ws, key=lambda w: w[0])) for _, ws in lines)

def pdf_pages(data: bytes) -> list[str]:
    import pymupdf
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [_reading_order(p) for p in doc]

def pdf_is_image_only(data: bytes) -> bool:
    import pymupdf
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return all(not p.get_text().strip() for p in doc)

# ---- XLSX -------------------------------------------------------------------------------------------------------------
def _cell_text(cell) -> str:
    v = cell.value
    if v is None:
        return ""
    fmt = cell.number_format or "General"
    prefix = ""
    m = re.match(r'^"([^"]*)"(.*)$', fmt)
    if m:
        prefix, fmt = m.group(1), m.group(2)
    if isinstance(v, datetime):
        return prefix + v.date().isoformat()
    if isinstance(v, date):
        return prefix + v.isoformat()
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        dp = len(fmt.split(".")[1]) if "." in fmt else 0
        return prefix + f"{Decimal(str(v)):.{dp}f}"
    return prefix + str(v)

def xlsx_pages(data: bytes) -> list[str]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    pages = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows():
            cells = [t for t in (_cell_text(c) for c in row) if t != ""]
            if cells:
                rows.append(SEP.join(cells))
        pages.append("\n".join(rows))
    return pages

# ---- email ------------------------------------------------------------------------------------------------------------
def parse_eml(data: bytes):
    return BytesParser(policy=policy.default).parsebytes(data)

def email_lines(msg) -> list[str]:
    name, addr = parseaddr(str(msg["From"]))
    out = [f"From: {name} <{addr}>", f"To: {msg['To']}"]
    if msg["Cc"]:
        out.append(f"Cc: {msg['Cc']}")
    dt = parsedate_to_datetime(str(msg["Date"]))
    out += [f"Date: {dt.strftime('%Y-%m-%dT%H:%M:%SZ')}", f"Subject: {msg['Subject']}", ""]
    body = msg.get_body(preferencelist=("plain",))
    out += body.get_content().replace("\r\n", "\n").rstrip("\n").split("\n") if body else []
    names = [p.get_filename() for p in msg.iter_attachments()]
    if names:
        out.append("Attachments: " + ", ".join(names))
    return out

def attachments(data: bytes) -> list[tuple[str, bytes]]:
    return [(p.get_filename() or "", p.get_content()) for p in parse_eml(data).iter_attachments()]

def pages_of(data: bytes, ext: str) -> list[str]:
    ext = ext.lower().lstrip(".")
    if ext == "pdf":
        return pdf_pages(data)
    if ext == "xlsx":
        return xlsx_pages(data)
    if ext == "eml":
        return ["\n".join(email_lines(parse_eml(data)))]
    raise ValueError(f"can't read .{ext} files")

# ---- batch reader -----------------------------------------------------------------------------------------------------
def read_batch(batch_dir: str) -> dict[str, tuple[list[str], bool]]:
    """Reads a batch directory and returns a dict mapping document reference to (pages, is_scan).
    
    A document reference is either:
    - 'batch_01/0014.eml'
    - 'batch_01/0014.eml#attachment.pdf'
    
    Returns:
    {
        "batch_01/0014.eml": (["From: ...\n\nBody..."], False),
        "batch_01/0014.eml#attachment.pdf": (["page1 text", "page2 text"], False)
    }
    """
    results = {}
    batch_path = Path(batch_dir)
    
    for eml_file in sorted(batch_path.rglob("*.eml")):
        # Calculate relative path (e.g., 'batch_01/0014.eml' or just '0014.eml' depending on batch_dir)
        # Assuming batch_dir is something like "data/scenarios/batch_01", we want the last part
        batch_name = batch_path.name
        rel_path = f"{batch_name}/{eml_file.name}"
        
        eml_bytes = eml_file.read_bytes()
        
        # Parse the email itself
        try:
            eml_pages = pages_of(eml_bytes, "eml")
            results[rel_path] = (eml_pages, False)
        except Exception as e:
            print(f"Failed to read EML {rel_path}: {e}")
            
        # Parse its attachments
        for att_name, att_bytes in attachments(eml_bytes):
            att_ref = f"{rel_path}#{att_name}"
            ext = att_name.rsplit(".", 1)[-1].lower() if "." in att_name else ""
            
            is_scan = False
            if ext == "pdf":
                try:
                    is_scan = pdf_is_image_only(att_bytes)
                except Exception:
                    is_scan = False
                    
            try:
                if not is_scan and ext in ("pdf", "xlsx"):
                    att_pages = pages_of(att_bytes, ext)
                    results[att_ref] = (att_pages, is_scan)
                else:
                    # If it's a scan or unknown extension, store empty pages but mark scan correctly
                    results[att_ref] = ([], is_scan)
            except Exception as e:
                print(f"Failed to read attachment {att_ref}: {e}")
                results[att_ref] = ([], False)
                
    return results
