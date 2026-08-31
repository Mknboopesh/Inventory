from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATA_FILE = ROOT / "data" / "database.json"
DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", ROOT / "generated-documents"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "inventory_management")
HASH_ITERATIONS = 25000
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_ATTEMPTS = 8
login_attempts: dict[str, list[datetime]] = {}

app = FastAPI(title="Inventory Management API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/generated-documents", StaticFiles(directory=DOCUMENTS_DIR), name="generated-documents")
DIST_DIR = ROOT / "frontend" / "dist"
if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="frontend-assets")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 http://localhost:5173 http://127.0.0.1:5173; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    return response


def now() -> str:
    return datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


def parse_iso(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except (TypeError, ValueError):
        return None


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def clean(value: Any) -> str:
    return str(value or "").strip()


def clean_name(value: Any) -> str:
    return clean(value).lower()


def local_xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def normalize_agent_url(value: Any) -> str:
    url = clean(value).rstrip("/")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ["http", "https"] or not parsed.netloc:
        raise HTTPException(400, "Enter a valid MTConnect Agent URL, for example http://192.168.1.20:5000.")
    return url


def number(value: Any) -> float:
    try:
        parsed = float(value)
        return parsed if parsed == parsed else 0
    except (TypeError, ValueError):
        return 0


def money(value: Any) -> float:
    return round(number(value), 2)


def pct(value: float) -> float:
    return round(max(0, min(100, value)), 1)


def safe_name(value: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", clean(value) or "document")
    safe = re.sub(r"\s+", "-", safe)
    return re.sub(r"-+", "-", safe)[:80] or "document"


def html(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def hash_password(password: str, salt: str | None = None, iterations: int = HASH_ITERATIONS) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt.encode(), iterations, 32).hex()
    return f"{iterations}:{salt}:{digest}"


def verify_password(password: str, stored: str) -> bool:
    parts = str(stored or "").split(":")
    candidates = []
    if len(parts) == 3:
        candidates.append((int(parts[0] or 0), parts[1], parts[2]))
    elif len(parts) == 2:
        candidates.append((120000, parts[0], parts[1]))
    for iterations, salt, digest in candidates:
        if not salt or not digest or iterations <= 0:
            continue
        check = hash_password(password, salt, iterations).split(":")[2]
        if hmac.compare_digest(check, digest):
            return True
    return False


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(400, "Password must contain letters and numbers.")


def check_login_rate_limit(request: Request, identity: str) -> None:
    host = request.client.host if request.client else "unknown"
    key = f"{host}:{clean_name(identity)}"
    cutoff = datetime.utcnow() - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    attempts = [item for item in login_attempts.get(key, []) if item > cutoff]
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(429, "Too many login attempts. Try again after 15 minutes.")
    attempts.append(datetime.utcnow())
    login_attempts[key] = attempts


def clear_login_rate_limit(request: Request, identity: str) -> None:
    host = request.client.host if request.client else "unknown"
    login_attempts.pop(f"{host}:{clean_name(identity)}", None)


def document_url(relative_path: str) -> str:
    return "/" + relative_path.replace("\\", "/")


def ensure_document_folders() -> None:
    folders = [
        "incoming-dc-invoices",
        "inward-grn-invoices",
        "outgoing-invoices",
        "ok-inspection-reports",
        "ok-dc-invoices",
        "not-ok-dc-invoices",
        "process-not-ok-dc",
        "machine-workflow/process-not-ok-dc",
        "machine-workflow/ok-inspection-reports",
        "machine-workflow/outgoing-dc-invoices",
        "machine-workflow/not-ok-dc-invoices",
        "machine-workflow/rejected-loss-dc",
        "machine-workflow/cnc-machining-documents",
    ]
    for folder in folders:
        (DOCUMENTS_DIR / folder).mkdir(parents=True, exist_ok=True)


client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2500)
db = client[DB_NAME]


def col(name: str):
    return db[name]


def strip_mongo_id(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    row = dict(row)
    row.pop("_id", None)
    return row


def rows(name: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [strip_mongo_id(row) for row in col(name).find(query or {})]


def one(name: str, query: dict[str, Any]) -> dict[str, Any] | None:
    return strip_mongo_id(col(name).find_one(query))


def save(name: str, row: dict[str, Any]) -> None:
    col(name).replace_one({"id": row["id"]}, row, upsert=True)


def public_company(company: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": company["id"],
        "name": company.get("name", ""),
        "address": company.get("address", ""),
        "phone": company.get("phone", ""),
        "email": company.get("email", ""),
        "ownerName": company.get("ownerName", ""),
    }


def public_user(user: dict[str, Any], company: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": user["id"],
        "role": user.get("role", ""),
        "name": user.get("name", ""),
        "phone": user.get("phone", ""),
        "email": user.get("email", ""),
        "status": user.get("status", ""),
        "ratePerHour": money(user.get("ratePerHour", 0)),
        "companyId": user.get("companyId", ""),
        "companyName": company.get("name", "") if company else "",
        "company": public_company(company) if company else None,
        "createdAt": user.get("createdAt", ""),
    }


def require_session(authorization: str | None, roles: list[str] | None = None) -> dict[str, Any]:
    token = clean((authorization or "").replace("Bearer ", ""))
    session = one("sessions", {"token": token}) if token else None
    if not session:
        raise HTTPException(401, "Please log in.")
    expires_at = parse_iso(session.get("expiresAt"))
    if expires_at and expires_at < datetime.utcnow():
        col("sessions").delete_many({"token": token})
        raise HTTPException(401, "Session expired. Please log in again.")
    user = one("users", {"id": session["userId"], "status": "approved"})
    company = one("companies", {"id": user.get("companyId")}) if user else None
    if not user or not company:
        raise HTTPException(401, "Please log in again.")
    if roles and user.get("role") not in roles:
        raise HTTPException(403, "You do not have access to this action.")
    return {"token": token, "user": user, "company": company}


def item_count(item: dict[str, Any]) -> int:
    return max(0, int(number(item.get("totalItems", item.get("quantity", 0)))))


def process_part_rows(item: dict[str, Any]) -> list[dict[str, Any]]:
    parts = item.get("parts") if isinstance(item.get("parts"), list) else []
    if not parts:
        parts = [
            {"partNo": index, "heatNo": heat_no}
            for index, heat_no in enumerate(heat_numbers_for_item(item), start=1)
        ]
    if not parts:
        parts = [{"partNo": index, "heatNo": item.get("heatNo", "")} for index in range(1, item_count(item) + 1)]
    normalized: list[dict[str, Any]] = []
    for index, part in enumerate(parts, start=1):
        status = clean_name(part.get("processStatus") or "pending")
        normalized.append({
            **part,
            "partNo": int(number(part.get("partNo")) or index),
            "heatNo": clean(part.get("heatNo") or item.get("heatNo")),
            "processStatus": status if status in ["pending", "ok", "rejected"] else "pending",
            "processRemarks": clean(part.get("processRemarks")),
            "processCheckedAt": part.get("processCheckedAt", ""),
            "processCheckedBy": part.get("processCheckedBy"),
        })
    return normalized


def process_counts(parts: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "pending": len([part for part in parts if part.get("processStatus", "pending") == "pending"]),
        "ok": len([part for part in parts if part.get("processStatus") == "ok"]),
        "rejected": len([part for part in parts if part.get("processStatus") == "rejected"]),
    }


def machining_quantity(item: dict[str, Any]) -> int:
    process_ok = int(number(item.get("processOkItems", 0)))
    return process_ok if process_ok > 0 else item_count(item)


def machining_part_rows(item: dict[str, Any]) -> list[dict[str, Any]]:
    parts = process_part_rows(item)
    if int(number(item.get("processOkItems", 0))) > 0:
        parts = [part for part in parts if part.get("processStatus") == "ok"]
    normalized: list[dict[str, Any]] = []
    for part in parts:
        default_status = "completed" if item.get("machiningStatus") == "completed" else "pending"
        status = clean_name(part.get("machiningStatus") or default_status)
        normalized.append({
            **part,
            "machiningStatus": status if status in ["pending", "completed"] else "pending",
            "machiningRemarks": clean(part.get("machiningRemarks")),
            "machiningCompletedAt": part.get("machiningCompletedAt", ""),
            "machiningCompletedBy": part.get("machiningCompletedBy"),
        })
    return normalized


def machining_counts(parts: list[dict[str, Any]]) -> dict[str, int]:
    completed = len([part for part in parts if part.get("machiningStatus") == "completed"])
    return {"pending": len(parts) - completed, "completed": completed}


def parse_part_heat_numbers(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = re.split(r"[\n,]+", str(value or ""))
    return [clean(item) for item in raw_values if clean(item)]


def heat_numbers_for_item(item: dict[str, Any]) -> list[str]:
    heat_numbers = item.get("heatNumbers")
    if isinstance(heat_numbers, list):
        values = [clean(value) for value in heat_numbers if clean(value)]
    else:
        values = []
    if clean(item.get("heatNo")) and clean(item.get("heatNo")) not in values:
        values.insert(0, clean(item.get("heatNo")))
    return values


def item_matches_heat(item: dict[str, Any], heat_no: str) -> bool:
    target = clean_name(heat_no)
    return bool(target) and any(clean_name(value) == target for value in heat_numbers_for_item(item))


def material_stage(item: dict[str, Any]) -> str:
    if item.get("processStatus") == "rejected":
        return "Rejected at quality check"
    if item.get("inspectionStatus") == "rejected":
        return "Rejected at inspection"
    if item.get("inspectionStatus") == "mixed":
        return "Mixed inspection"
    if item.get("inspectionStatus") == "ok":
        return "Inspection OK"
    if item.get("machiningStatus") == "completed":
        return "Inspection pending"
    if item.get("machiningStatus") == "in_machining":
        return "Machining"
    return "Quality pending"


def write_document(folder: str, file_name: str, content: str) -> dict[str, Any]:
    target_dir = DOCUMENTS_DIR / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    name = safe_name(file_name)
    if not name.endswith(".html"):
        name += ".html"
    target = target_dir / name
    target.write_text(content, encoding="utf-8")
    relative = str(Path("generated-documents") / folder / name)
    return {"name": name, "relativePath": relative, "url": document_url(relative)}


def machining_document_html(record: dict[str, Any]) -> str:
    company = record.get("company", {})
    runs = record.get("runs", [])
    rows_html = "".join(
        "<tr>"
        f"<td>{html(run.get('machinedAt'))}</td>"
        f"<td>{html(run.get('machineName'))}</td>"
        f"<td>{html(run.get('program'))}</td>"
        f"<td>{html(run.get('execution'))}</td>"
        f"<td>{html(run.get('partCount'))}</td>"
        f"<td>{html(run.get('operator', {}).get('name'))}</td>"
        f"<td>{html(run.get('remarks'))}</td>"
        "</tr>"
        for run in runs
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>CNC Machining Document - {html(record.get('heatNo'))}</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;color:#172033}}table{{width:100%;border-collapse:collapse;margin-top:22px}}td,th{{border:1px solid #d8e4f8;padding:10px;text-align:left}}.meta{{line-height:1.7}}.badge{{display:inline-block;border:1px solid #bfdbfe;border-radius:999px;background:#eff6ff;color:#1d4ed8;padding:5px 10px;font-weight:700}}</style></head>
<body><h1>CNC Machining Document</h1>
<p class="meta"><strong>{html(company.get('name',''))}</strong><br>{html(company.get('address',''))}<br>{html(company.get('phone',''))}</p>
<p><span class="badge">Heat no: {html(record.get('heatNo'))}</span></p>
<p class="meta"><strong>Drawing:</strong> {html(record.get('drawingNo'))}<br><strong>Description:</strong> {html(record.get('productDescription'))}<br><strong>Total runs:</strong> {len(runs)}<br><strong>Last updated:</strong> {html(record.get('updatedAt'))}</p>
<table><thead><tr><th>Machined at</th><th>CNC machine</th><th>Program</th><th>Execution</th><th>Part count</th><th>Operator</th><th>Remarks</th></tr></thead><tbody>{rows_html}</tbody></table>
</body></html>"""


def invoice_html(invoice: dict[str, Any], title: str) -> str:
    company = invoice.get("company", {})
    heat_numbers = invoice.get("heatNumbers") or []
    heat_html = ""
    if heat_numbers:
        heat_rows = "".join(
            f"<tr><td>Part {index}</td><td>{html(heat_no)}</td></tr>"
            for index, heat_no in enumerate(heat_numbers, start=1)
        )
        heat_html = f"<h2>Part heat numbers</h2><table><thead><tr><th>Part</th><th>Heat no</th></tr></thead><tbody>{heat_rows}</tbody></table>"
    rows_html = "".join(
        f"<tr><td>{html(item.get('description'))}</td><td>{html(item.get('quantity'))}</td>"
        f"<td>Rs. {number(item.get('rate')):.2f}</td><td>Rs. {number(item.get('amount')):.2f}</td></tr>"
        for item in invoice.get("items", [])
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html(title)}</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;color:#172033}}table{{width:100%;border-collapse:collapse;margin-top:22px}}td,th{{border:1px solid #d8e4f8;padding:10px;text-align:left}}.total{{font-size:20px;font-weight:700;text-align:right}}</style></head>
<body><h1>{html(title)}</h1><p><strong>{html(company.get('name',''))}</strong><br>{html(company.get('address',''))}<br>{html(company.get('phone',''))}</p>
<p><strong>Invoice:</strong> {html(invoice.get('invoiceNumber'))}<br><strong>Date:</strong> {html(invoice.get('createdAt'))}<br><strong>Customer:</strong> {html(invoice.get('customerName') or 'Walk-in')}<br><strong>Heat no:</strong> {html(invoice.get('heatNoDisplay') or invoice.get('heatNo') or '')}</p>
{heat_html}
<table><thead><tr><th>Description</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead><tbody>{rows_html}</tbody></table>
<p class="total">Total: Rs. {number(invoice.get('total')):.2f}</p></body></html>"""


def add_doc(item: dict[str, Any], doc: dict[str, Any]) -> None:
    docs = item.setdefault("generatedDocuments", [])
    if not any(existing.get("type") == doc.get("type") and existing.get("name") == doc.get("name") for existing in docs):
        docs.append(doc)


def has_doc(item: dict[str, Any], doc_type: str) -> bool:
    return any(doc.get("type") == doc_type for doc in item.get("generatedDocuments", []))


def create_invoice(session: dict[str, Any], item: dict[str, Any], invoice_type: str, quantity: int, title: str, folder: str) -> dict[str, Any]:
    rate = money(item.get("ratePerItem", item.get("unitPrice", 0)))
    heat_numbers = heat_numbers_for_item(item)
    invoice = {
        "id": new_id("inv"),
        "invoiceNumber": f"{title.split()[0].upper()}-{int(datetime.utcnow().timestamp() * 1000)}",
        "type": invoice_type,
        "companyId": session["company"]["id"],
        "company": public_company(session["company"]),
        "createdBy": public_user(session["user"], session["company"]),
        "customerName": item.get("customerName", ""),
        "customerPhone": item.get("customerPhone", ""),
        "heatNo": item.get("heatNo", ""),
        "heatNumbers": heat_numbers,
        "heatNoDisplay": ", ".join(heat_numbers),
        "hsCode": item.get("hsCode", ""),
        "totalItems": quantity,
        "quantity": quantity,
        "ratePerItem": rate,
        "total": money(quantity * rate),
        "items": [{"description": item.get("productDescription", "Material"), "quantity": quantity, "rate": rate, "amount": money(quantity * rate)}],
        "createdAt": now(),
    }
    invoice["document"] = write_document(folder, invoice["invoiceNumber"], invoice_html(invoice, title))
    save("invoices", invoice)
    return invoice


def create_machining_completed_invoice(session: dict[str, Any], item: dict[str, Any], quantity: int) -> dict[str, Any] | None:
    if quantity <= 0 or has_doc(item, "working_material_invoice"):
        return None
    invoice = create_invoice(session, item, "working_material_invoice", quantity, "Machining Completed Invoice", "outgoing-invoices")
    add_doc(item, {"type": "working_material_invoice", "title": f"Machining completed invoice - {quantity} item(s)", **invoice["document"]})
    item["workingMaterialInvoiceItems"] = quantity
    return invoice


def upsert_cnc_machining_document(session: dict[str, Any], item: dict[str, Any], heat_no: str, machine: dict[str, Any] | None, body: dict[str, Any]) -> dict[str, Any]:
    heat_no = clean(heat_no)
    if not heat_no:
        raise HTTPException(400, "Heat no is required for CNC machining.")
    if int(number(item.get("processOkItems", 0))) > 0:
        ok_heat_numbers = [
            clean(part.get("heatNo"))
            for part in process_part_rows(item)
            if part.get("processStatus") == "ok" and clean(part.get("heatNo"))
        ]
        if clean_name(heat_no) not in [clean_name(value) for value in ok_heat_numbers]:
            raise HTTPException(400, "This heat no was not marked OK in process.")
    elif not item_matches_heat(item, heat_no):
        raise HTTPException(400, "This heat no is not available in the selected material.")

    machine_status = fetch_mtconnect_status(machine) if machine else {}
    current = machine_status.get("current", {}) if machine_status.get("connected") else {}
    run = {
        "id": new_id("run"),
        "machinedAt": now(),
        "machineId": machine.get("id", "") if machine else "",
        "machineName": machine.get("name", "") if machine else clean(body.get("machineName")),
        "machineState": machine_status.get("state", ""),
        "program": clean(body.get("program")) or clean(current.get("program")),
        "execution": clean(current.get("execution")),
        "partCount": clean(body.get("partCount")) or clean(current.get("partCount")),
        "feedrate": clean(current.get("pathFeedrate")),
        "spindleSpeed": clean(current.get("spindleSpeed")),
        "remarks": clean(body.get("remarks")),
        "operator": public_user(session["user"], session["company"]),
    }
    existing = one("cncMachiningDocuments", {"companyId": session["company"]["id"], "heatNoKey": clean_name(heat_no)})
    if existing:
        record = existing
        runs = record.setdefault("runs", [])
        runs.append(run)
        record.update({
            "drawingNo": item.get("drawingNo", record.get("drawingNo", "")),
            "productDescription": item.get("productDescription", record.get("productDescription", "")),
            "inventoryItemId": item.get("id", record.get("inventoryItemId", "")),
            "lastMachineName": run["machineName"],
            "updatedBy": public_user(session["user"], session["company"]),
            "updatedAt": now(),
        })
    else:
        record = {
            "id": new_id("cncdoc"),
            "companyId": session["company"]["id"],
            "company": public_company(session["company"]),
            "inventoryItemId": item.get("id", ""),
            "heatNo": heat_no,
            "heatNoKey": clean_name(heat_no),
            "drawingNo": item.get("drawingNo", ""),
            "productDescription": item.get("productDescription", ""),
            "lastMachineName": run["machineName"],
            "runs": [run],
            "createdBy": public_user(session["user"], session["company"]),
            "createdAt": now(),
            "updatedAt": now(),
        }
    document = write_document("machine-workflow/cnc-machining-documents", f"CNC-MACHINING-{heat_no}", machining_document_html(record))
    record["document"] = document
    save("cncMachiningDocuments", record)
    return record


def generate_final_documents(session: dict[str, Any], item: dict[str, Any], create_hs_bill: bool = False) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    total = item_count(item)
    process_rejected = int(number(item.get("processRejectedItems", 0)))
    if (item.get("processStatus") == "rejected" or process_rejected > 0) and not has_doc(item, "process_rejected_loss_dc"):
        rejected_total = process_rejected or total
        invoice = create_invoice(session, item, "process_rejected_loss_dc", rejected_total, "Rejected Loss DC", "machine-workflow/rejected-loss-dc")
        doc = {"type": "process_rejected_loss_dc", "title": f"Rejected loss DC - {rejected_total} item(s)", **invoice["document"]}
        add_doc(item, doc)
        created.append(doc)
    ok_units = int(number(item.get("okItems", total if item.get("inspectionStatus") == "ok" else 0)))
    not_ok_units = int(number(item.get("notOkItems", total if item.get("inspectionStatus") == "rejected" else 0)))
    if ok_units > 0 and not has_doc(item, "ok_inspection_report"):
        report = write_document("machine-workflow/ok-inspection-reports", f"OK-{item.get('heatNo','report')}-{ok_units}", invoice_html({
            "invoiceNumber": f"OK-{item.get('heatNo','')}",
            "company": public_company(session["company"]),
            "customerName": item.get("customerName", ""),
            "items": [{"description": f"OK inspection report - {item.get('productDescription','')}", "quantity": ok_units, "rate": 0, "amount": 0}],
            "total": 0,
            "createdAt": now(),
        }, "OK Inspection Report"))
        doc = {"type": "ok_inspection_report", "title": f"OK inspection report - {ok_units} items", **report}
        add_doc(item, doc)
        created.append(doc)
    if not_ok_units > 0 and not has_doc(item, "not_ok_loss_dc"):
        invoice = create_invoice(session, item, "not_ok_loss_dc", not_ok_units, "Not OK DC", "machine-workflow/not-ok-dc-invoices")
        doc = {"type": "not_ok_loss_dc", "title": f"Not OK DC - {not_ok_units} items", **invoice["document"]}
        add_doc(item, doc)
        created.append(doc)
    if create_hs_bill and ok_units > 0 and not has_doc(item, "hs_ok_bill"):
        invoice = create_invoice(session, item, "hs_ok_bill", ok_units, "HS OK Bill", "machine-workflow/outgoing-dc-invoices")
        doc = {"type": "hs_ok_bill", "title": f"HS bill {item.get('hsCode','')} - {ok_units} OK items", **invoice["document"]}
        add_doc(item, doc)
        created.append(doc)
    return created


def public_mtconnect_machine(machine: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": machine.get("id", ""),
        "name": machine.get("name", ""),
        "agentUrl": machine.get("agentUrl", ""),
        "deviceName": machine.get("deviceName", ""),
        "createdAt": machine.get("createdAt", ""),
        "updatedAt": machine.get("updatedAt", ""),
    }


def parse_mtconnect_current(xml_text: str) -> dict[str, Any]:
    root = ElementTree.fromstring(xml_text)
    values: dict[str, Any] = {}
    conditions: list[dict[str, str]] = []
    observations: list[dict[str, str]] = []

    for element in root.iter():
        text = clean(element.text)
        if not text:
            continue
        tag = local_xml_name(element.tag)
        key = clean(element.attrib.get("name")) or clean(element.attrib.get("dataItemId")) or tag
        record = {
            "tag": tag,
            "name": key,
            "value": text,
            "timestamp": clean(element.attrib.get("timestamp")),
        }
        observations.append(record)
        values[key.lower()] = text
        values[tag.lower()] = text
        if tag in ["Normal", "Warning", "Fault", "Unavailable"]:
            conditions.append({
                "level": tag,
                "name": key,
                "value": text,
                "timestamp": record["timestamp"],
            })

    def pick(*keys: str) -> str:
        for key in keys:
            value = values.get(key.lower())
            if value:
                return value
        return ""

    return {
        "availability": pick("availability"),
        "execution": pick("execution"),
        "controllerMode": pick("controller_mode", "controllermode", "ControllerMode"),
        "program": pick("program", "program_name", "programname"),
        "partCount": pick("part_count", "partcount"),
        "pathFeedrate": pick("path_feedrate", "pathfeedrate", "feedrate"),
        "spindleSpeed": pick("spindle_speed", "spindlespeed"),
        "emergencyStop": pick("emergency_stop", "emergencystop"),
        "conditions": conditions[:12],
        "observations": observations[:80],
    }


def fetch_mtconnect_status(machine: dict[str, Any]) -> dict[str, Any]:
    url = f"{machine.get('agentUrl', '').rstrip('/')}/current"
    status = {
        **public_mtconnect_machine(machine),
        "connected": False,
        "state": "offline",
        "message": "",
        "lastCheckedAt": now(),
        "current": {},
    }
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/xml,text/xml,*/*"})
        with urllib.request.urlopen(request, timeout=4) as response:
            xml_text = response.read(2_000_000).decode("utf-8", errors="replace")
        current = parse_mtconnect_current(xml_text)
        availability = clean_name(current.get("availability"))
        execution = clean_name(current.get("execution"))
        emergency_stop = clean_name(current.get("emergencyStop"))
        state = "available" if availability == "available" else "unavailable"
        if emergency_stop and emergency_stop not in ["armed", "normal"]:
            state = "alarm"
        elif execution:
            state = execution.replace("_", " ")
        status.update({"connected": True, "state": state, "message": "Connected", "current": current})
    except (urllib.error.URLError, TimeoutError, ElementTree.ParseError, OSError) as error:
        status["message"] = str(error)
    return status


def ai_order_advisor(company_id: str) -> dict[str, Any]:
    inventory = rows("inventory", {"companyId": company_id})
    purchase_orders = rows("purchaseOrders", {"companyId": company_id})
    invoices = rows("invoices", {"companyId": company_id})
    salary_records = rows("salaryRecords", {"companyId": company_id})
    cnc_documents = rows("cncMachiningDocuments", {"companyId": company_id})

    po_by_drawing = {clean_name(po.get("drawingNo")): po for po in purchase_orders if clean(po.get("drawingNo"))}
    invoice_counts: dict[str, int] = {}
    for invoice in invoices:
        for item in invoice.get("items", []):
            key = clean_name(item.get("description"))
            if key:
                invoice_counts[key] = invoice_counts.get(key, 0) + int(number(item.get("quantity", 1)) or 1)

    model_rows: dict[str, dict[str, Any]] = {}
    for item in inventory:
        drawing = clean(item.get("drawingNo")) or "Unknown drawing"
        key = clean_name(drawing)
        qty = int(number(item.get("totalItems", item.get("quantity", 0))))
        rate = money(item.get("ratePerItem", 0))
        po = po_by_drawing.get(key, {})
        final_rate = money(po.get("finalRate") or rate)
        production_rate = money(po.get("productionRate"))
        inward_rate = money(po.get("rateOnInward") or rate)
        estimated_cost = money(max(production_rate, inward_rate, rate * 0.65))
        margin_per_item = money(max(0, final_rate - estimated_cost))
        total_margin = money(margin_per_item * qty)
        ok_items = int(number(item.get("okItems", 0)))
        not_ok_items = int(number(item.get("notOkItems", 0)))
        produced = ok_items + not_ok_items
        demand_units = qty + invoice_counts.get(clean_name(item.get("productDescription")), 0)
        bucket = model_rows.setdefault(key, {
            "drawingNo": drawing,
            "description": clean(item.get("productDescription")) or "Material",
            "orders": 0,
            "quantity": 0,
            "okItems": 0,
            "notOkItems": 0,
            "estimatedRevenue": 0.0,
            "estimatedProfit": 0.0,
            "demandUnits": 0,
            "latestAt": "",
        })
        bucket["orders"] += 1
        bucket["quantity"] += qty
        bucket["okItems"] += ok_items
        bucket["notOkItems"] += not_ok_items
        bucket["estimatedRevenue"] += final_rate * qty
        bucket["estimatedProfit"] += total_margin
        bucket["demandUnits"] += demand_units
        bucket["latestAt"] = max(bucket["latestAt"], clean(item.get("createdAt")))

    recommendations: list[dict[str, Any]] = []
    max_profit = max([row["estimatedProfit"] for row in model_rows.values()] + [1])
    max_demand = max([row["demandUnits"] for row in model_rows.values()] + [1])
    for row in model_rows.values():
        total_checked = row["okItems"] + row["notOkItems"]
        quality_score = (row["okItems"] / total_checked * 100) if total_checked else 72
        profit_score = row["estimatedProfit"] / max_profit * 100
        demand_score = row["demandUnits"] / max_demand * 100
        repeat_score = min(100, row["orders"] * 22)
        risk_penalty = max(0, 100 - quality_score) * 0.35
        score = pct((profit_score * 0.42) + (demand_score * 0.28) + (quality_score * 0.20) + (repeat_score * 0.10) - risk_penalty)
        if score >= 72:
            action = "Take more orders"
        elif score >= 52:
            action = "Take selective orders"
        else:
            action = "Review before taking order"
        recommendations.append({
            "drawingNo": row["drawingNo"],
            "description": row["description"],
            "orders": row["orders"],
            "quantity": row["quantity"],
            "estimatedRevenue": money(row["estimatedRevenue"]),
            "estimatedProfit": money(row["estimatedProfit"]),
            "profitPerItem": money(row["estimatedProfit"] / max(1, row["quantity"])),
            "qualityScore": pct(quality_score),
            "demandScore": pct(demand_score),
            "profitScore": pct(profit_score),
            "aiScore": score,
            "action": action,
            "reason": f"Profit score {pct(profit_score)}%, demand score {pct(demand_score)}%, quality score {pct(quality_score)}%.",
        })

    recommendations.sort(key=lambda item: item["aiScore"], reverse=True)
    top_profit = sorted(recommendations, key=lambda item: item["estimatedProfit"], reverse=True)[:5]
    new_order_ideas = [item for item in recommendations if item["aiScore"] >= 52][:8]
    rejection_risks = sorted(
        [item for item in recommendations if item["qualityScore"] < 80],
        key=lambda item: item["qualityScore"],
    )[:5]
    process_rows = build_process_model(inventory)
    machining_rows = build_machining_model(inventory, cnc_documents)

    total_profit = sum(item["estimatedProfit"] for item in recommendations)
    total_revenue = sum(item["estimatedRevenue"] for item in recommendations)
    salary_cost = sum(money(record.get("totalSalary", 0)) for record in salary_records)
    return {
        "model": {
            "name": "Inventory Order Advisor v1",
            "type": "local agentic scoring model",
            "trainedOn": {
                "inventoryItems": len(inventory),
                "purchaseOrders": len(purchase_orders),
                "invoices": len(invoices),
                "salaryRecords": len(salary_records),
            },
            "lastRunAt": now(),
        },
        "models": {
            "order": {
                "name": "Inventory Order Advisor v1",
                "type": "profit and demand scoring model",
                "itemsScored": len(recommendations),
            },
            "process": {
                "name": "Process Quality Model v1",
                "type": "incoming material approval and rejection scoring model",
                "itemsScored": len(process_rows),
            },
            "machining": {
                "name": "Machining Readiness Model v1",
                "type": "CNC readiness and completion scoring model",
                "itemsScored": len(machining_rows),
            },
        },
        "summary": {
            "estimatedRevenue": money(total_revenue),
            "estimatedProfit": money(total_profit),
            "salaryCost": money(salary_cost),
            "netAfterSalary": money(total_profit - salary_cost),
            "bestItem": top_profit[0]["description"] if top_profit else "",
            "processBacklog": sum(row["pendingQuantity"] for row in process_rows),
            "machiningBacklog": sum(row["inMachiningQuantity"] for row in machining_rows),
        },
        "recommendations": recommendations,
        "topProfitItems": top_profit,
        "newOrderIdeas": new_order_ideas,
        "riskWarnings": rejection_risks,
        "processModel": process_rows[:8],
        "machiningModel": machining_rows[:8],
        "guidance": [
            "Prefer high AI score items when accepting new orders.",
            "If quality score is low, improve machining/inspection before increasing order quantity.",
            "Use profit per item and repeat demand together; high demand with low margin can still reduce profit.",
        ],
    }


def build_process_model(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in inventory:
        drawing = clean(item.get("drawingNo")) or "Unknown drawing"
        key = clean_name(drawing)
        qty = int(number(item.get("totalItems", item.get("quantity", 0))))
        status = clean_name(item.get("processStatus") or "pending")
        bucket = buckets.setdefault(key, {
            "drawingNo": drawing,
            "description": clean(item.get("productDescription")) or "Material",
            "orders": 0,
            "quantity": 0,
            "pendingQuantity": 0,
            "approvedQuantity": 0,
            "rejectedQuantity": 0,
            "latestAt": "",
        })
        bucket["orders"] += 1
        bucket["quantity"] += qty
        if status == "ok":
            bucket["approvedQuantity"] += qty
        elif status == "rejected":
            bucket["rejectedQuantity"] += qty
        else:
            bucket["pendingQuantity"] += qty
        bucket["latestAt"] = max(bucket["latestAt"], clean(item.get("createdAt")))

    model: list[dict[str, Any]] = []
    for row in buckets.values():
        decided = row["approvedQuantity"] + row["rejectedQuantity"]
        approval_score = (row["approvedQuantity"] / decided * 100) if decided else 70
        backlog_score = 100 if row["quantity"] <= 0 else max(0, 100 - (row["pendingQuantity"] / row["quantity"] * 100))
        rejection_penalty = (row["rejectedQuantity"] / max(1, row["quantity"])) * 45
        score = pct((approval_score * 0.58) + (backlog_score * 0.42) - rejection_penalty)
        if row["pendingQuantity"]:
            action = "Prioritize process check"
        elif row["rejectedQuantity"]:
            action = "Review supplier or material issue"
        else:
            action = "Process flow is healthy"
        model.append({
            **row,
            "approvalScore": pct(approval_score),
            "backlogScore": pct(backlog_score),
            "aiScore": score,
            "action": action,
            "reason": f"{row['pendingQuantity']} pending, {row['approvedQuantity']} approved, {row['rejectedQuantity']} rejected.",
            "metrics": [
                f"Pending {row['pendingQuantity']}",
                f"Approved {row['approvedQuantity']}",
                f"Rejected {row['rejectedQuantity']}",
                f"Approval {pct(approval_score)}%",
            ],
        })
    model.sort(key=lambda item: (item["pendingQuantity"], item["aiScore"]), reverse=True)
    return model


def build_machining_model(inventory: list[dict[str, Any]], cnc_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runs_by_item: dict[str, int] = {}
    for document in cnc_documents:
        item_id = clean(document.get("inventoryItemId"))
        if item_id:
            runs_by_item[item_id] = runs_by_item.get(item_id, 0) + len(document.get("runs", []))

    buckets: dict[str, dict[str, Any]] = {}
    for item in inventory:
        drawing = clean(item.get("drawingNo")) or "Unknown drawing"
        key = clean_name(drawing)
        qty = machining_quantity(item)
        status = clean_name(item.get("machiningStatus") or "waiting")
        part_counts = machining_counts(machining_part_rows(item))
        bucket = buckets.setdefault(key, {
            "drawingNo": drawing,
            "description": clean(item.get("productDescription")) or "Material",
            "orders": 0,
            "quantity": 0,
            "waitingQuantity": 0,
            "inMachiningQuantity": 0,
            "completedQuantity": 0,
            "cncRuns": 0,
            "assignedMachines": set(),
            "latestAt": "",
        })
        bucket["orders"] += 1
        bucket["quantity"] += qty
        bucket["cncRuns"] += runs_by_item.get(clean(item.get("id")), 0)
        if clean(item.get("mtconnectMachineName")):
            bucket["assignedMachines"].add(clean(item.get("mtconnectMachineName")))
        if status == "completed":
            bucket["completedQuantity"] += qty
        elif status == "in_machining":
            bucket["completedQuantity"] += part_counts["completed"]
            bucket["inMachiningQuantity"] += part_counts["pending"]
        else:
            bucket["waitingQuantity"] += qty
        bucket["latestAt"] = max(bucket["latestAt"], clean(item.get("createdAt")))

    model: list[dict[str, Any]] = []
    for row in buckets.values():
        completion_score = (row["completedQuantity"] / row["quantity"] * 100) if row["quantity"] else 0
        run_score = min(100, row["cncRuns"] * 18)
        machine_score = min(100, len(row["assignedMachines"]) * 35)
        active_penalty = (row["inMachiningQuantity"] / max(1, row["quantity"])) * 20
        score = pct((completion_score * 0.55) + (run_score * 0.25) + (machine_score * 0.20) - active_penalty)
        if row["inMachiningQuantity"]:
            action = "Track active machining"
        elif row["waitingQuantity"]:
            action = "Assign CNC before machining"
        else:
            action = "Ready for inspection or dispatch"
        machines = sorted(row["assignedMachines"])
        row["assignedMachines"] = machines
        model.append({
            **row,
            "completionScore": pct(completion_score),
            "runScore": pct(run_score),
            "machineScore": pct(machine_score),
            "aiScore": score,
            "action": action,
            "reason": f"{row['completedQuantity']} completed, {row['inMachiningQuantity']} in machining, {row['cncRuns']} CNC run(s).",
            "metrics": [
                f"In machining {row['inMachiningQuantity']}",
                f"Completed {row['completedQuantity']}",
                f"CNC runs {row['cncRuns']}",
                f"Machines {len(machines)}",
            ],
        })
    model.sort(key=lambda item: (item["inMachiningQuantity"], item["waitingQuantity"], item["aiScore"]), reverse=True)
    return model


def erp_overview(company_id: str) -> dict[str, Any]:
    inventory = rows("inventory", {"companyId": company_id})
    purchase_orders = rows("purchaseOrders", {"companyId": company_id})
    invoices = rows("invoices", {"companyId": company_id})
    salary_records = rows("salaryRecords", {"companyId": company_id})
    sales_orders = rows("salesOrders", {"companyId": company_id})
    expenses = rows("expenses", {"companyId": company_id})
    revenue = sum(money(invoice.get("total", 0)) for invoice in invoices) + sum(money(order.get("totalValue", 0)) for order in sales_orders)
    procurement_value = sum(money(order.get("finalRate", 0)) for order in purchase_orders)
    salary_cost = sum(money(record.get("totalSalary", 0)) for record in salary_records)
    operating_expense = sum(money(expense.get("amount", 0)) for expense in expenses)
    return {
        "summary": {
            "revenue": money(revenue),
            "procurementValue": money(procurement_value),
            "salaryCost": money(salary_cost),
            "operatingExpense": money(operating_expense),
            "estimatedNet": money(revenue - salary_cost - operating_expense),
            "openSalesOrders": len([order for order in sales_orders if order.get("status") not in ["completed", "cancelled"]]),
            "pendingProduction": len([item for item in inventory if item.get("machiningStatus") in ["waiting", "in_machining"]]),
        },
        "salesOrders": sales_orders,
        "expenses": expenses,
        "purchaseOrders": purchase_orders,
        "inventory": [{**item, "stage": material_stage(item)} for item in inventory],
        "invoices": invoices,
        "salaryRecords": salary_records,
    }


def public_process_material(item: dict[str, Any]) -> dict[str, Any]:
    qty = item_count(item)
    parts = process_part_rows(item)
    counts = process_counts(parts)
    return {
        "id": item.get("id", ""),
        "itemId": item.get("id", ""),
        "processCode": f"PROC-{clean(item.get('materialCode')) or clean(item.get('id'))}",
        "materialCode": item.get("materialCode", ""),
        "drawingNo": item.get("drawingNo", ""),
        "description": item.get("productDescription", ""),
        "productDescription": item.get("productDescription", ""),
        "material": item.get("material", ""),
        "heatNo": item.get("heatNo", ""),
        "heatNumbers": heat_numbers_for_item(item),
        "parts": parts,
        "quantity": qty,
        "totalItems": qty,
        "pendingParts": counts["pending"],
        "okParts": counts["ok"],
        "rejectedParts": counts["rejected"],
        "receivedAt": item.get("grnDateTime") or item.get("createdAt", ""),
        "processStatus": item.get("processStatus", "pending"),
        "processRemarks": item.get("processRemarks", ""),
        "stage": "Process pending",
        "generatedDocuments": item.get("generatedDocuments", []),
    }


def public_machining_job(item: dict[str, Any]) -> dict[str, Any]:
    qty = machining_quantity(item)
    process_ok_items = int(number(item.get("processOkItems", 0)))
    machining_parts = machining_part_rows(item)
    counts = machining_counts(machining_parts)
    heat_numbers = [part.get("heatNo", "") for part in machining_parts if clean(part.get("heatNo"))]
    return {
        "id": item.get("id", ""),
        "itemId": item.get("id", ""),
        "jobNo": f"MC-{clean(item.get('materialCode')) or clean(item.get('id'))}",
        "materialCode": item.get("materialCode", ""),
        "drawingNo": item.get("drawingNo", ""),
        "description": item.get("productDescription", ""),
        "productDescription": item.get("productDescription", ""),
        "heatNo": heat_numbers[0] if heat_numbers else item.get("heatNo", ""),
        "heatNumbers": heat_numbers or heat_numbers_for_item(item),
        "parts": machining_parts,
        "quantity": qty,
        "totalItems": qty,
        "pendingMachiningParts": counts["pending"],
        "completedMachiningParts": counts["completed"],
        "processOkItems": process_ok_items or qty,
        "processRejectedItems": int(number(item.get("processRejectedItems", 0))),
        "machineId": item.get("mtconnectMachineId", ""),
        "machineName": item.get("mtconnectMachineName", ""),
        "mtconnectMachineId": item.get("mtconnectMachineId", ""),
        "mtconnectMachineName": item.get("mtconnectMachineName", ""),
        "lastCncHeatNo": item.get("lastCncHeatNo", ""),
        "lastCncMachiningDocumentId": item.get("lastCncMachiningDocumentId", ""),
        "lastCncMachiningAt": item.get("lastCncMachiningAt", ""),
        "machiningStatus": item.get("machiningStatus", "waiting"),
        "inspectionStatus": item.get("inspectionStatus", "pending"),
        "processCheckedAt": item.get("processCheckedAt", ""),
        "stage": material_stage(item),
        "generatedDocuments": item.get("generatedDocuments", []),
    }


@app.on_event("startup")
def startup() -> None:
    client.admin.command("ping")
    ensure_document_folders()
    if col("companies").count_documents({}) == 0 and DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for name in ["companies", "users", "inventory", "purchaseOrders", "invoices", "salaryRecords", "sessions", "mtconnectMachines", "cncMachiningDocuments", "salesOrders", "expenses"]:
            records = data.get(name, [])
            if records:
                col(name).insert_many(records)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": DB_NAME}


@app.get("/api/companies")
def companies() -> dict[str, Any]:
    return {"companies": [public_company(company) for company in rows("companies")]}


@app.post("/api/auth/owner-register", status_code=201)
async def owner_register(request: Request) -> dict[str, str]:
    body = await request.json()
    company_name = clean(body.get("companyName"))
    address = clean(body.get("address"))
    name = clean(body.get("name"))
    phone = clean(body.get("phone"))
    email = clean(body.get("email"))
    password = clean(body.get("password"))
    if not all([company_name, address, name, phone, email]) or len(password) < 6:
        raise HTTPException(400, "Company name, address, owner name, phone, email, and a 6 character password are required.")
    validate_password(password)
    if any(clean_name(c.get("name")) == clean_name(company_name) for c in rows("companies")):
        raise HTTPException(409, "That company is already registered.")
    company = {"id": new_id("cmp"), "name": company_name, "address": address, "phone": phone, "email": email, "ownerName": name, "createdAt": now()}
    user = {"id": new_id("usr"), "companyId": company["id"], "role": "owner", "name": name, "phone": phone, "email": email, "passwordHash": hash_password(password), "status": "approved", "createdAt": now()}
    save("companies", company)
    save("users", user)
    return {"message": "Company registered. Owner can log in now."}


@app.post("/api/auth/staff-register", status_code=201)
async def staff_register(request: Request) -> dict[str, str]:
    body = await request.json()
    company_name = clean(body.get("companyName"))
    role = clean_name(body.get("role"))
    name = clean(body.get("name"))
    phone = clean(body.get("phone"))
    email = clean(body.get("email"))
    password = clean(body.get("password"))
    if role not in ["manager", "employee"]:
        raise HTTPException(400, "Choose manager or employee.")
    if not company_name or not name or not phone or len(password) < 6:
        raise HTTPException(400, "Company name, name, phone, and a 6 character password are required.")
    validate_password(password)
    company = next((c for c in rows("companies") if clean_name(c.get("name")) == clean_name(company_name)), None)
    if not company:
        raise HTTPException(404, "No owner has registered that company yet.")
    user = {"id": new_id("usr"), "companyId": company["id"], "role": role, "name": name, "phone": phone, "email": email, "passwordHash": hash_password(password), "status": "pending", "createdAt": now()}
    save("users", user)
    return {"message": "Registration sent. Please wait for owner approval."}


@app.post("/api/auth/login")
async def login(request: Request) -> dict[str, Any]:
    body = await request.json()
    company = next((c for c in rows("companies") if clean_name(c.get("name")) == clean_name(body.get("companyName"))), None)
    if not company:
        raise HTTPException(404, "Company not found.")
    identity = clean_name(body.get("identity"))
    check_login_rate_limit(request, identity)
    user = next((u for u in rows("users", {"companyId": company["id"]}) if clean_name(u.get("email")) == identity or clean_name(u.get("phone")) == identity), None)
    if not user or not verify_password(clean(body.get("password")), user.get("passwordHash", "")):
        raise HTTPException(401, "Invalid login details.")
    if user.get("status") != "approved":
        raise HTTPException(403, "Your request is waiting for owner approval." if user.get("status") == "pending" else "Your request was rejected.")
    token = new_id("ses")
    clear_login_rate_limit(request, identity)
    col("sessions").delete_many({"userId": user["id"]})
    expires_at = (datetime.utcnow() + timedelta(hours=SESSION_HOURS)).isoformat(timespec="milliseconds") + "Z"
    save("sessions", {"id": token, "token": token, "userId": user["id"], "createdAt": now(), "expiresAt": expires_at})
    return {"token": token, "user": public_user(user, company)}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = clean((authorization or "").replace("Bearer ", ""))
    if token:
        col("sessions").delete_many({"token": token})
    return {"message": "Logged out."}


@app.get("/api/me")
def me(session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization))) -> dict[str, Any]:
    return {"user": public_user(session["user"], session["company"])}


@app.get("/api/dashboard")
def dashboard(session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    company_id = session["company"]["id"]
    users = rows("users", {"companyId": company_id})
    inventory = rows("inventory", {"companyId": company_id})
    invoices = rows("invoices", {"companyId": company_id})
    salary_records = rows("salaryRecords", {"companyId": company_id})
    purchase_orders = rows("purchaseOrders", {"companyId": company_id})
    machines = rows("mtconnectMachines", {"companyId": company_id})
    return {
        "company": public_company(session["company"]),
        "stats": {
            "items": len(inventory),
            "totalUnits": sum(number(i.get("quantity", i.get("totalItems", 0))) for i in inventory),
            "managers": len([u for u in users if u.get("role") == "manager" and u.get("status") == "approved"]),
            "employees": len([u for u in users if u.get("role") == "employee" and u.get("status") == "approved"]),
            "pendingRequests": len([u for u in users if u.get("status") == "pending"]),
            "invoices": len(invoices),
            "salaryRecords": len(salary_records),
            "processPending": sum(process_counts(process_part_rows(i))["pending"] for i in inventory if i.get("processStatus", "pending") == "pending"),
            "machining": len([i for i in inventory if i.get("machiningStatus") == "in_machining"]),
            "inspectionPending": len([i for i in inventory if i.get("machiningStatus") == "completed" and i.get("inspectionStatus", "pending") == "pending"]),
            "rejected": len([i for i in inventory if i.get("processStatus") == "rejected" or i.get("inspectionStatus") == "rejected"]),
            "okItems": sum(number(i.get("okItems", 0)) for i in inventory),
            "notOkItems": sum(number(i.get("notOkItems", 0)) for i in inventory),
        },
        "purchaseOrders": purchase_orders,
        "inventory": [{**item, "stage": material_stage(item)} for item in inventory],
        "processMaterials": [
            public_process_material(item)
            for item in inventory
            if item.get("processStatus", "pending") == "pending"
        ],
        "machiningJobs": [
            public_machining_job(item)
            for item in inventory
            if item.get("processStatus") == "ok" and item.get("machiningStatus") in ["waiting", "in_machining", "completed"]
        ],
        "invoices": invoices,
        "salaryRecords": salary_records,
        "mtconnectMachines": [public_mtconnect_machine(machine) for machine in machines],
    }


@app.get("/api/ai/advisor")
def ai_advisor(session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    return ai_order_advisor(session["company"]["id"])


@app.get("/api/erp/overview")
def erp_dashboard(session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    return erp_overview(session["company"]["id"])


@app.post("/api/erp/sales-orders", status_code=201)
async def create_sales_order(request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    quantity = int(number(body.get("quantity")))
    rate = money(body.get("rate"))
    order = {
        "id": new_id("so"),
        "companyId": session["company"]["id"],
        "orderNumber": f"SO-{int(datetime.utcnow().timestamp() * 1000)}",
        "customerName": clean(body.get("customerName")),
        "customerPhone": clean(body.get("customerPhone")),
        "drawingNo": clean(body.get("drawingNo")),
        "description": clean(body.get("description")),
        "quantity": quantity,
        "rate": rate,
        "totalValue": money(quantity * rate),
        "dueDate": clean(body.get("dueDate")),
        "status": "open",
        "createdBy": public_user(session["user"], session["company"]),
        "createdAt": now(),
        "updatedAt": now(),
    }
    if not order["customerName"] or not order["drawingNo"] or not order["description"] or quantity <= 0 or rate <= 0:
        raise HTTPException(400, "Customer, drawing no, description, quantity, and rate are required.")
    save("salesOrders", order)
    return {"order": order, "message": "Sales order saved."}


@app.patch("/api/erp/sales-orders/{order_id}/status")
async def update_sales_order_status(order_id: str, request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    status = clean_name((await request.json()).get("status"))
    if status not in ["open", "in_production", "completed", "cancelled"]:
        raise HTTPException(400, "Status must be open, in production, completed, or cancelled.")
    order = one("salesOrders", {"id": order_id, "companyId": session["company"]["id"]})
    if not order:
        raise HTTPException(404, "Sales order not found.")
    order["status"] = status
    order["updatedAt"] = now()
    save("salesOrders", order)
    return {"order": order, "message": "Sales order status updated."}


@app.post("/api/erp/expenses", status_code=201)
async def create_expense(request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    amount = money(body.get("amount"))
    expense = {
        "id": new_id("exp"),
        "companyId": session["company"]["id"],
        "expenseDate": clean(body.get("expenseDate")) or datetime.utcnow().date().isoformat(),
        "category": clean(body.get("category")),
        "description": clean(body.get("description")),
        "amount": amount,
        "paidBy": clean(body.get("paidBy")),
        "createdBy": public_user(session["user"], session["company"]),
        "createdAt": now(),
        "updatedAt": now(),
    }
    if not expense["category"] or not expense["description"] or amount <= 0:
        raise HTTPException(400, "Category, description, and amount are required.")
    save("expenses", expense)
    return {"expense": expense, "message": "Expense saved."}


@app.get("/api/users")
def users(role: str | None = None, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    company_users = rows("users", {"companyId": session["company"]["id"]})
    if session["user"]["role"] == "manager":
        company_users = [user for user in company_users if user.get("role") == "employee"]
    if role:
        company_users = [user for user in company_users if user.get("role") == role]
    return {"users": [public_user(user, session["company"]) for user in company_users]}


@app.patch("/api/users/{user_id}/status")
async def update_user_status(user_id: str, request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner"]))) -> dict[str, Any]:
    status = clean_name((await request.json()).get("status"))
    if status not in ["approved", "rejected"]:
        raise HTTPException(400, "Status must be approved or rejected.")
    user = one("users", {"id": user_id, "companyId": session["company"]["id"]})
    if not user or user.get("role") == "owner":
        raise HTTPException(404, "User request not found.")
    user["status"] = status
    save("users", user)
    return {"user": public_user(user, session["company"])}


@app.get("/api/mtconnect/machines")
def mtconnect_machines(session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    machines = rows("mtconnectMachines", {"companyId": session["company"]["id"]})
    return {"machines": [public_mtconnect_machine(machine) for machine in machines]}


@app.post("/api/mtconnect/machines", status_code=201)
async def create_mtconnect_machine(request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    name = clean(body.get("name"))
    agent_url = normalize_agent_url(body.get("agentUrl"))
    device_name = clean(body.get("deviceName"))
    if not name:
        raise HTTPException(400, "Machine name is required.")
    machine = {
        "id": new_id("cnc"),
        "companyId": session["company"]["id"],
        "name": name,
        "agentUrl": agent_url,
        "deviceName": device_name,
        "createdBy": public_user(session["user"], session["company"]),
        "createdAt": now(),
        "updatedAt": now(),
    }
    save("mtconnectMachines", machine)
    return {"machine": public_mtconnect_machine(machine), "message": "CNC machine connected."}


@app.delete("/api/mtconnect/machines/{machine_id}")
def delete_mtconnect_machine(machine_id: str, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, str]:
    machine = one("mtconnectMachines", {"id": machine_id, "companyId": session["company"]["id"]})
    if not machine:
        raise HTTPException(404, "CNC machine not found.")
    col("mtconnectMachines").delete_one({"id": machine_id, "companyId": session["company"]["id"]})
    col("inventory").update_many(
        {"companyId": session["company"]["id"], "mtconnectMachineId": machine_id},
        {"$unset": {"mtconnectMachineId": "", "mtconnectMachineName": ""}, "$set": {"updatedAt": now()}},
    )
    return {"message": "CNC machine removed."}


@app.get("/api/mtconnect/machines/status")
def mtconnect_machine_statuses(session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    machines = rows("mtconnectMachines", {"companyId": session["company"]["id"]})
    return {"machines": [fetch_mtconnect_status(machine) for machine in machines]}


@app.get("/api/mtconnect/machines/{machine_id}/status")
def mtconnect_machine_status(machine_id: str, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    machine = one("mtconnectMachines", {"id": machine_id, "companyId": session["company"]["id"]})
    if not machine:
        raise HTTPException(404, "CNC machine not found.")
    return {"machine": fetch_mtconnect_status(machine)}


@app.post("/api/purchase-orders", status_code=201)
async def purchase_order(request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    order = {
        "id": new_id("po"),
        "companyId": session["company"]["id"],
        "drawingNo": clean(body.get("drawingNo")),
        "productionRate": money(body.get("productionRate")),
        "companyName": clean(body.get("companyName")),
        "rateOnInward": money(body.get("rateOnInward")),
        "finalRate": money(body.get("finalRate")),
        "createdBy": public_user(session["user"], session["company"]),
        "createdAt": now(),
        "updatedAt": now(),
    }
    if not order["drawingNo"] or not order["companyName"]:
        raise HTTPException(400, "Drawing no and company name are required.")
    save("purchaseOrders", order)
    return {"order": order, "message": "Purchase order saved."}


@app.post("/api/inventory/arrival", status_code=201)
async def inventory_arrival(request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    qty = int(number(body.get("totalItems", body.get("quantity"))))
    rate = money(body.get("ratePerItem", body.get("ratePerPiece")))
    heat_numbers = parse_part_heat_numbers(body.get("heatNumbers") or body.get("partHeatNumbers") or body.get("heatNo"))
    if qty > 0 and len(heat_numbers) == 1 and qty > 1:
        heat_numbers = heat_numbers * qty
    parts = [{"partNo": index, "heatNo": heat_no} for index, heat_no in enumerate(heat_numbers, start=1)]
    item = {
        "id": new_id("mat"),
        "companyId": session["company"]["id"],
        "materialCode": f"MAT-{int(datetime.utcnow().timestamp() * 1000)}",
        "productDescription": clean(body.get("productDescription") or body.get("description")),
        "heatNo": heat_numbers[0] if heat_numbers else "",
        "heatNumbers": heat_numbers,
        "parts": parts,
        "drawingNo": clean(body.get("drawingNo")),
        "material": clean(body.get("material")),
        "grnDate": clean(body.get("grnDate")),
        "grnTime": clean(body.get("grnTime")),
        "grnDateTime": f"{clean(body.get('grnDate'))}T{clean(body.get('grnTime'))}:00",
        "hsCode": clean(body.get("hsCode")),
        "totalItems": qty,
        "runItems": 0,
        "remainingItems": qty,
        "ratePerItem": rate,
        "totalValue": money(qty * rate),
        "customerName": clean(body.get("customerName")),
        "customerPhone": clean(body.get("customerPhone")),
        "processStatus": "pending",
        "machiningStatus": "waiting",
        "inspectionStatus": "pending",
        "createdBy": public_user(session["user"], session["company"]),
        "createdAt": now(),
        "updatedAt": now(),
    }
    if not item["productDescription"] or not item["drawingNo"] or not item["material"] or not item["hsCode"] or qty <= 0:
        raise HTTPException(400, "Description, drawing no, material, HS code, quantity, and rate per piece are required.")
    if len(heat_numbers) != qty:
        raise HTTPException(400, f"Enter one heat no for each part. Quantity is {qty}, but {len(heat_numbers)} heat no value(s) were entered.")
    invoice = create_invoice(session, item, "inward_grn", qty, "Inward GRN Invoice", "inward-grn-invoices")
    item["dcInvoiceNumber"] = invoice["invoiceNumber"]
    add_doc(item, {"type": "inward_grn_invoice", "title": "Inward GRN invoice", **invoice["document"]})
    save("inventory", item)
    return {"item": item, "invoice": invoice, "message": f"GRN saved. Inward GRN invoice stored in {invoice['document']['relativePath']}."}


@app.patch("/api/inventory/{item_id}/process")
async def update_process(item_id: str, request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    decision = clean_name(body.get("decision"))
    if decision not in ["ok", "rejected"]:
        raise HTTPException(400, "Process decision must be OK or rejected.")
    part_no = int(number(body.get("partNo", 0)))
    item = one("inventory", {"id": item_id, "companyId": session["company"]["id"]})
    if not item:
        raise HTTPException(404, "Material not found.")
    checked_at = now()
    checker = public_user(session["user"], session["company"])
    parts = process_part_rows(item)
    if part_no:
        part = next((row for row in parts if int(number(row.get("partNo"))) == part_no), None)
        if not part:
            raise HTTPException(404, "Part not found.")
        part.update({
            "processStatus": decision,
            "processRemarks": clean(body.get("remarks")),
            "processCheckedBy": checker,
            "processCheckedAt": checked_at,
        })
    else:
        for part in parts:
            part.update({
                "processStatus": decision,
                "processRemarks": clean(body.get("remarks")),
                "processCheckedBy": checker,
                "processCheckedAt": checked_at,
            })

    counts = process_counts(parts)
    if counts["pending"] > 0:
        process_status = "pending"
        process_result = "partial_check"
        machining_status = item.get("machiningStatus", "waiting")
        message = f"Part {part_no} marked {decision.upper()}. {counts['pending']} part(s) still pending."
    else:
        process_status = "ok" if counts["ok"] > 0 else "rejected"
        process_result = "mixed" if counts["ok"] and counts["rejected"] else process_status
        machining_status = "in_machining" if counts["ok"] > 0 else "not_applicable"
        if process_result == "mixed":
            message = f"Process completed: {counts['ok']} OK part(s), {counts['rejected']} rejected part(s). OK parts sent for machining."
        elif process_status == "ok":
            message = "All parts are OK. Material sent for machining."
        else:
            message = "All parts rejected. Rejected invoice stored."

    item.update({
        "parts": parts,
        "processStatus": process_status,
        "processResult": process_result,
        "processRemarks": clean(body.get("remarks")),
        "processCheckedBy": checker,
        "processCheckedAt": checked_at,
        "machiningStatus": machining_status,
        "processOkItems": counts["ok"],
        "processRejectedItems": counts["rejected"],
        "okItems": 0,
        "notOkItems": counts["rejected"] if process_status == "rejected" else int(number(item.get("notOkItems", 0))),
        "updatedAt": checked_at,
    })
    if counts["pending"] == 0:
        generate_final_documents(session, item)
    save("inventory", item)
    return {"item": {**item, "stage": material_stage(item)}, "message": message}


@app.patch("/api/inventory/{item_id}/machine")
async def assign_mtconnect_machine(item_id: str, request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    machine_id = clean(body.get("machineId"))
    item = one("inventory", {"id": item_id, "companyId": session["company"]["id"]})
    if not item:
        raise HTTPException(404, "Material not found.")
    if item.get("machiningStatus") not in ["waiting", "in_machining", "completed"]:
        raise HTTPException(400, "Only machining materials can be assigned to a CNC machine.")
    if not machine_id:
        item.pop("mtconnectMachineId", None)
        item.pop("mtconnectMachineName", None)
        item["updatedAt"] = now()
        save("inventory", item)
        return {"item": {**item, "stage": material_stage(item)}, "message": "CNC machine assignment removed."}
    machine = one("mtconnectMachines", {"id": machine_id, "companyId": session["company"]["id"]})
    if not machine:
        raise HTTPException(404, "CNC machine not found.")
    item.update({
        "mtconnectMachineId": machine["id"],
        "mtconnectMachineName": machine.get("name", ""),
        "machineAssignedBy": public_user(session["user"], session["company"]),
        "machineAssignedAt": now(),
        "updatedAt": now(),
    })
    save("inventory", item)
    return {"item": {**item, "stage": material_stage(item)}, "message": f"Assigned to {machine.get('name', 'CNC machine')}."}


@app.post("/api/inventory/{item_id}/cnc-machining", status_code=201)
async def save_cnc_machining(item_id: str, request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    heat_no = clean(body.get("heatNo"))
    machine_id = clean(body.get("machineId"))
    item = one("inventory", {"id": item_id, "companyId": session["company"]["id"]})
    if not item:
        raise HTTPException(404, "Material not found.")
    if item.get("machiningStatus") not in ["waiting", "in_machining", "completed"]:
        raise HTTPException(400, "Only machining materials can save CNC heat no documents.")
    machine = one("mtconnectMachines", {"id": machine_id, "companyId": session["company"]["id"]}) if machine_id else None
    if machine_id and not machine:
        raise HTTPException(404, "CNC machine not found.")
    record = upsert_cnc_machining_document(session, item, heat_no, machine, body)
    add_doc(item, {
        "type": "cnc_machining_document",
        "title": f"CNC machining document - {record['heatNo']}",
        **record["document"],
    })
    item["lastCncHeatNo"] = record["heatNo"]
    item["lastCncMachiningDocumentId"] = record["id"]
    item["lastCncMachiningAt"] = record["updatedAt"]
    item["updatedAt"] = now()
    save("inventory", item)
    return {
        "item": {**item, "stage": material_stage(item)},
        "document": record["document"],
        "message": f"CNC machining document saved for heat no {record['heatNo']}.",
    }


@app.patch("/api/inventory/{item_id}/machining")
async def update_machining(item_id: str, request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    part_no = int(number(body.get("partNo", 0)))
    item = one("inventory", {"id": item_id, "companyId": session["company"]["id"]})
    if not item:
        raise HTTPException(404, "Material not found.")
    if item.get("processStatus") != "ok":
        raise HTTPException(400, "Only quality OK materials can complete machining.")
    if process_counts(process_part_rows(item))["pending"] > 0:
        raise HTTPException(400, "Complete processing for every part before machining.")
    completed_at = now()
    operator = public_user(session["user"], session["company"])
    parts = process_part_rows(item)
    machinable_part_numbers = {
        int(number(part.get("partNo")))
        for part in machining_part_rows(item)
    }
    if part_no:
        if part_no not in machinable_part_numbers:
            raise HTTPException(404, "Machining part not found.")
        for part in parts:
            if int(number(part.get("partNo"))) == part_no:
                part.update({
                    "machiningStatus": "completed",
                    "machiningRemarks": clean(body.get("remarks")),
                    "machiningCompletedBy": operator,
                    "machiningCompletedAt": completed_at,
                })
                break
    else:
        for part in parts:
            if int(number(part.get("partNo"))) in machinable_part_numbers:
                part.update({
                    "machiningStatus": "completed",
                    "machiningRemarks": clean(body.get("remarks")),
                    "machiningCompletedBy": operator,
                    "machiningCompletedAt": completed_at,
                })

    item["parts"] = parts
    counts = machining_counts(machining_part_rows(item))
    all_completed = counts["pending"] == 0
    item.update({
        "machiningStatus": "completed" if all_completed else "in_machining",
        "inspectionStatus": "pending",
        "machiningRemarks": clean(body.get("remarks")),
        "machiningCompletedBy": operator,
        "machiningCompletedAt": completed_at if all_completed else item.get("machiningCompletedAt", ""),
        "machiningCompletedItems": counts["completed"],
        "updatedAt": completed_at,
    })
    invoice = create_machining_completed_invoice(session, item, counts["completed"]) if all_completed else None
    save("inventory", item)
    if all_completed:
        message = "All machining parts completed. Machining completed invoice generated."
    else:
        message = f"Part {part_no} machining completed. {counts['pending']} part(s) still pending."
    return {"item": {**item, "stage": material_stage(item)}, "invoice": invoice, "message": message}


@app.patch("/api/inventory/{item_id}/inspection")
async def update_inspection(item_id: str, request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    item = one("inventory", {"id": item_id, "companyId": session["company"]["id"]})
    if not item:
        raise HTTPException(404, "Material not found.")
    if item.get("machiningStatus") != "completed":
        raise HTTPException(400, "Complete machining before inspection.")
    total = machining_quantity(item)
    ok_items = int(number(body.get("okItems", 0)))
    not_ok_items = int(number(body.get("notOkItems", 0)))
    if ok_items or not_ok_items:
        if ok_items + not_ok_items != total:
            raise HTTPException(400, f"OK items and not OK items must total {total}.")
        status = "mixed" if ok_items and not_ok_items else ("ok" if ok_items == total else "rejected")
    else:
        decision = clean_name(body.get("decision"))
        if decision not in ["ok", "rejected"]:
            raise HTTPException(400, "Inspection decision must be OK or rejected.")
        ok_items = total if decision == "ok" else 0
        not_ok_items = total if decision == "rejected" else 0
        status = decision
    item.update({"okItems": ok_items, "notOkItems": not_ok_items, "inspectionStatus": status, "inspectionRemarks": clean(body.get("remarks")), "inspectedBy": public_user(session["user"], session["company"]), "inspectedAt": now(), "updatedAt": now()})
    generate_final_documents(session, item)
    save("inventory", item)
    return {"item": {**item, "stage": material_stage(item)}, "message": "Inspection count saved. Enter HS code from Generate HS total bill to create the single customer invoice."}


@app.post("/api/inventory/{item_id}/documents/generate")
async def generate_documents(item_id: str, request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    item = one("inventory", {"id": item_id, "companyId": session["company"]["id"]})
    if not item:
        raise HTTPException(404, "Material not found.")
    if clean(body.get("hsCode")):
        item["hsCode"] = clean(body.get("hsCode"))
    created = generate_final_documents(session, item, create_hs_bill=True)
    item["updatedAt"] = now()
    save("inventory", item)
    return {"item": {**item, "stage": material_stage(item)}, "message": f"Generated {len(created)} file(s) for this item." if created else "Documents already generated."}


@app.patch("/api/inventory/working-material")
async def working_material(request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    heat_no = clean_name(body.get("heatNo"))
    run_items = int(number(body.get("runItems")))
    item = next((i for i in rows("inventory", {"companyId": session["company"]["id"]}) if item_matches_heat(i, heat_no)), None)
    if not item:
        raise HTTPException(404, "No working material found with that heat no.")
    available = int(number(item.get("okItems") if item.get("inspectionStatus") == "mixed" else item.get("totalItems")))
    if run_items < 0 or run_items > available:
        raise HTTPException(400, f"Run items must be between 0 and {available}.")
    item["runItems"] = run_items
    item["remainingItems"] = available - run_items
    item["workingMaterialUpdatedAt"] = now()
    save("inventory", item)
    return {"item": {**item, "stage": material_stage(item)}, "message": f"Working material updated for heat no {item.get('heatNo')}."}


@app.post("/api/inventory/working-material/invoice", status_code=201)
async def working_material_invoice(request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    heat_no = clean_name((await request.json()).get("heatNo"))
    item = next((i for i in rows("inventory", {"companyId": session["company"]["id"]}) if item_matches_heat(i, heat_no)), None)
    if not item:
        raise HTTPException(404, "No working material found with that heat no.")
    completed = int(number(item.get("runItems")))
    if completed <= 0:
        raise HTTPException(400, "Update run/dispatched items before generating the invoice.")
    invoice = create_machining_completed_invoice(session, item, completed)
    save("inventory", item)
    return {"item": {**item, "stage": material_stage(item)}, "invoice": invoice, "message": "Machining completed invoice generated."}


@app.post("/api/salary", status_code=201)
async def salary(request: Request, session: dict[str, Any] = Depends(lambda authorization=Header(default=None): require_session(authorization, ["owner", "manager"]))) -> dict[str, Any]:
    body = await request.json()
    employee = one("users", {"id": clean(body.get("employeeId")), "companyId": session["company"]["id"], "role": "employee", "status": "approved"})
    if not employee:
        raise HTTPException(404, "Approved employee not found.")
    rate = money(body.get("ratePerHour") or employee.get("ratePerHour", 0))
    in_time = clean(body.get("inTime"))
    out_time = clean(body.get("outTime"))
    try:
        start = datetime.fromisoformat(in_time)
        end = datetime.fromisoformat(out_time)
    except ValueError:
        raise HTTPException(400, "Enter a valid in time and out time.")
    hours = max(0, (end - start).total_seconds() / 3600)
    record = {"id": new_id("sal"), "companyId": session["company"]["id"], "employeeId": employee["id"], "employeeName": employee["name"], "ratePerHour": rate, "inTime": in_time, "outTime": out_time, "hours": round(hours, 2), "totalSalary": money(hours * rate), "createdBy": public_user(session["user"], session["company"]), "createdAt": now()}
    employee["ratePerHour"] = rate
    save("users", employee)
    save("salaryRecords", record)
    return {"record": record, "message": "Salary calculated and saved."}


@app.get("/{full_path:path}", response_class=HTMLResponse)
def frontend_fallback(full_path: str):
    index = ROOT / "frontend" / "dist" / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(404, "Frontend build not found. Run `npm run build` inside frontend.")
