import os
import sys
import json
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom

from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


class _SafeEncoder(json.JSONEncoder):
    """Converts numpy scalar types that are not natively JSON-serializable."""
    def default(self, obj):
        import numpy as np
        if isinstance(obj, np.bool_):   return bool(obj)
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        return super().default(obj)


# ---------------------------------------------------------------------------
# Tally export helpers (mirrored from main.py so the API can save them too)
# ---------------------------------------------------------------------------

def _save_tally_csv(df, path: str) -> None:
    import pandas as pd
    tally = df[["Date", "Clean_Description", "CoA_Category", "Debit", "Credit"]].copy()
    tally["Date"] = df["Date"].dt.strftime("%d/%m/%Y")
    tally["Voucher_Type"] = tally.apply(lambda r: "Payment" if r["Debit"] > 0 else "Receipt", axis=1)
    tally["Amount"] = tally.apply(lambda r: r["Debit"] if r["Debit"] > 0 else r["Credit"], axis=1)
    tally = tally.rename(columns={"Clean_Description": "Ledger_Name"})
    tally[["Date", "Voucher_Type", "Ledger_Name", "CoA_Category", "Amount"]].to_csv(path, index=False)


def _save_tally_xml(df, path: str) -> None:
    envelope = ET.Element("ENVELOPE")
    header = ET.SubElement(envelope, "HEADER")
    ET.SubElement(header, "TALLYREQUEST").text = "Import Data"
    body = ET.SubElement(envelope, "BODY")
    importdata = ET.SubElement(body, "IMPORTDATA")
    reqdesc = ET.SubElement(importdata, "REQUESTDESC")
    ET.SubElement(reqdesc, "REPORTNAME").text = "Vouchers"
    staticvars = ET.SubElement(reqdesc, "STATICVARIABLES")
    ET.SubElement(staticvars, "SVCURRENTCOMPANY").text = "My Company"
    reqdata = ET.SubElement(importdata, "REQUESTDATA")

    for _, row in df.iterrows():
        if row["Debit"] == 0 and row["Credit"] == 0:
            continue
        tmsg = ET.SubElement(reqdata, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        vchtype = "Payment" if row["Debit"] > 0 else "Receipt"
        amt = row["Debit"] if row["Debit"] > 0 else row["Credit"]
        voucher = ET.SubElement(tmsg, "VOUCHER", {"VCHTYPE": vchtype, "ACTION": "Create"})
        ET.SubElement(voucher, "DATE").text = row["Date"].strftime("%Y%m%d")
        ET.SubElement(voucher, "VOUCHERTYPENAME").text = vchtype
        ET.SubElement(voucher, "NARRATION").text = str(row.get("Clean_Description", ""))
        party = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(party, "LEDGERNAME").text = str(row.get("Clean_Description", ""))
        ET.SubElement(party, "ISDEEMEDPOSITIVE").text = "Yes" if vchtype == "Payment" else "No"
        ET.SubElement(party, "AMOUNT").text = f"-{amt}" if vchtype == "Payment" else f"{amt}"
        bank = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(bank, "LEDGERNAME").text = "HDFC Bank"
        ET.SubElement(bank, "ISDEEMEDPOSITIVE").text = "No" if vchtype == "Payment" else "Yes"
        ET.SubElement(bank, "AMOUNT").text = f"{amt}" if vchtype == "Payment" else f"-{amt}"

    xml_str = minidom.parseString(ET.tostring(envelope)).toprettyxml(indent="  ")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_str)


# ---------------------------------------------------------------------------
# Metrics computation (from uploaded file's dataframe only)
# ---------------------------------------------------------------------------

def _compute_metrics(df) -> dict:
    import pandas as pd
    import numpy as np

    df = df.copy().sort_values("Date").reset_index(drop=True)

    total_inflow  = float(df["Credit"].sum())
    total_outflow = float(df["Debit"].sum())
    net           = total_inflow - total_outflow
    current_bal   = float(df.iloc[-1]["Balance"])

    date_min = df["Date"].min()
    date_max = df["Date"].max()
    days = max(1, (date_max - date_min).days)

    daily_burn   = total_outflow / days
    monthly_burn = daily_burn * 30
    runway_days  = (current_bal / daily_burn) if daily_burn > 0 else 9999.0
    health = "CRITICAL" if runway_days < 30 else ("WARNING" if runway_days < 90 else "HEALTHY")

    # ── Monthly trends ──────────────────────────────────────────────────────
    df["_period"] = df["Date"].dt.to_period("M")
    monthly = (
        df.groupby("_period")
        .agg(inflow=("Credit", "sum"), outflow=("Debit", "sum"))
        .reset_index()
    )
    monthly["net"] = monthly["inflow"] - monthly["outflow"]
    monthly["month"] = monthly["_period"].dt.strftime("%b %Y")
    monthly_trends = [
        {
            "month":   row["month"],
            "inflow":  round(float(row["inflow"]), 2),
            "outflow": round(float(row["outflow"]), 2),
            "net":     round(float(row["net"]), 2),
        }
        for _, row in monthly.iterrows()
    ]

    # ── P&L ─────────────────────────────────────────────────────────────────
    contras   = ["Fund Transfer", "Cash Deposit", "Credit Card Repayment", "Loan & EMI"]
    income_df = df[(df["Credit"] > 0) & (~df["CoA_Category"].isin(contras))]
    opex_cats = [
        "Payroll", "Fuel & Auto", "Healthcare & Medical", "Utilities & Telecom",
        "Software & IT", "UPI & Digital Payment", "E-Commerce & Retail",
        "Travel & Transport", "IMPS Transfer",
    ]
    opex_df       = df[(df["Debit"] > 0) & (df["CoA_Category"].isin(opex_cats))]
    fin_df        = df[(df["Debit"] > 0) & (df["CoA_Category"].isin(["Bank Charges & Fees"]))]
    total_income  = float(income_df["Credit"].sum())
    total_opex    = float(opex_df["Debit"].sum())
    total_finance = float(fin_df["Debit"].sum())
    gross_profit  = total_income - (total_opex + total_finance)

    cash_df          = df[(df["Debit"] > 0) & (df["CoA_Category"] == "ATM Withdrawal")]
    total_cash_drawn = float(cash_df["Debit"].sum())

    # ── Crisis ───────────────────────────────────────────────────────────────
    ess_cats = ["Payroll", "Healthcare & Medical", "Utilities & Telecom",
                "Software & IT", "Bank Charges & Fees", "Credit Card Repayment", "Loan & EMI"]
    ess_df           = df[(df["Debit"] > 0) & (df["CoA_Category"].isin(ess_cats))]
    daily_crisis     = float(ess_df["Debit"].sum()) / days
    monthly_crisis   = daily_crisis * 30
    crisis_runway    = (current_bal / daily_crisis) if daily_crisis > 0 else 9999.0

    # ── Top vendors ──────────────────────────────────────────────────────────
    outflows   = df[df["Debit"] > 0]
    vendor_grp = (
        outflows.groupby("Clean_Description")["Debit"]
        .agg(["sum", "count"]).reset_index()
        .sort_values("sum", ascending=False)
    )
    top_vendors = [
        {
            "vendor_name":               str(row["Clean_Description"]),
            "total_spend":               round(float(row["sum"]), 2),
            "transaction_count":         int(row["count"]),
            "percentage_of_total_outflow": round(float(row["sum"] / total_outflow * 100), 2) if total_outflow > 0 else 0.0,
        }
        for _, row in vendor_grp.head(10).iterrows()
    ]

    # ── Recurring subscriptions ──────────────────────────────────────────────
    subs_grp  = outflows.groupby(["Clean_Description", "Debit"]).size().reset_index(name="count")
    recurring = subs_grp[subs_grp["count"] >= 2].sort_values("Debit", ascending=False)
    noise     = {"ATM WITHDRAWAL", "CASH DEPOSIT", "UPI TRANSFER"}
    detected_subs = [
        {
            "vendor_name":      str(row["Clean_Description"]),
            "recurring_amount": round(float(row["Debit"]), 2),
            "times_detected":   int(row["count"]),
        }
        for _, row in recurring.iterrows()
        if not any(n in str(row["Clean_Description"]).upper() for n in noise)
    ]
    fixed_monthly = sum(s["recurring_amount"] for s in detected_subs)

    # ── Category breakdown ───────────────────────────────────────────────────
    cat_counts = [
        {"category": str(cat), "count": int(cnt)}
        for cat, cnt in df["CoA_Category"].value_counts().items()
    ]

    return {
        "summary": {
            "total_transactions": int(len(df)),
            "latest_balance":     round(current_bal, 2),
            "total_inflow":       round(total_inflow, 2),
            "total_outflow":      round(total_outflow, 2),
            "net_cash_flow":      round(net, 2),
            "date_range": {
                "start": date_min.strftime("%Y-%m-%d"),
                "end":   date_max.strftime("%Y-%m-%d"),
            },
        },
        "runway_and_burn_rate": {
            "daily_burn_rate":        round(daily_burn, 2),
            "monthly_burn_rate":      round(monthly_burn, 2),
            "average_monthly_inflow": round((total_inflow / days) * 30, 2),
            "current_balance":        round(current_bal, 2),
            "runway_days_left":       round(runway_days, 1),
            "health_status":          health,
        },
        "draft_pnl_statement": {
            "Total_Income":           round(total_income, 2),
            "Operating_Expenses":     round(total_opex, 2),
            "Financial_Expenses":     round(total_finance, 2),
            "Gross_Estimated_Profit": round(gross_profit, 2),
            "Non_PnL_Outflows": {"Cash_Drawings": round(total_cash_drawn, 2)},
        },
        "crisis_survival_mode": {
            "essential_monthly_overhead":    round(monthly_crisis, 2),
            "crisis_runway_days_left":       round(crisis_runway, 1),
            "total_tracked_essential_spend": round(float(ess_df["Debit"].sum()), 2),
        },
        "cash_withdrawal_tracker": {
            "total_cash_withdrawn": round(total_cash_drawn, 2),
            "tds_194N_limit":       2000000.0,
            "limit_remaining":      round(max(0.0, 2000000.0 - total_cash_drawn), 2),
            "warning_active":       total_cash_drawn >= 2000000.0,
        },
        "vendor_dependency": {
            "total_tracked_vendors": int(len(vendor_grp)),
            "top_vendors":           top_vendors,
        },
        "recurring_subscriptions": {
            "total_recurring_subscriptions_found": len(detected_subs),
            "estimated_fixed_monthly_cost":         round(fixed_monthly, 2),
            "detected_subscriptions":               detected_subs,
        },
        "monthly_trends":    monthly_trends,
        "category_breakdown": cat_counts,
    }


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def _run_pipeline(file_path: str) -> dict:
    from dotenv import load_dotenv
    load_dotenv()

    from core.extractors.hdfc_pdf import HDFCPDFExtractor
    from core.processors.cleaner import HDFCDataCleaner
    from core.processors.sanitizer import DataSanitizer
    from core.ai_services.coa_mapper import CoAMapper
    from core.db.session import init_db
    from core.db.operations import upsert_transactions
    from core.ai_services.insights_generator import InsightsGenerator

    OUT_DIR       = os.path.join("data", "output")
    INSIGHTS_PATH = os.path.join(OUT_DIR, "financial_insights.md")
    TALLY_CSV     = os.path.join(OUT_DIR, "tally_import.csv")
    TALLY_XML     = os.path.join(OUT_DIR, "tally_import.xml")
    os.makedirs(OUT_DIR, exist_ok=True)

    init_db()

    # Extract
    if file_path.lower().endswith(".pdf"):
        raw_data = HDFCPDFExtractor(file_path).extract() or []
    else:
        from core.extractors.image_ocr import ImageOCRExtractor
        raw_data = ImageOCRExtractor(image_paths=[file_path]).extract() or []

    if not raw_data:
        return {"error": "Extraction returned no data. Check the file format or bank statement layout."}

    clean_df = HDFCDataCleaner(raw_data).clean()
    if clean_df.empty:
        return {"error": "Cleaning step produced no valid rows. The PDF may be scanned or image-based."}

    safe_df = DataSanitizer(clean_df).scrub_pii()

    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        safe_df = CoAMapper(api_key=groq_api_key).map(safe_df)
    else:
        safe_df["CoA_Category"]     = "Uncategorized"
        safe_df["Confidence_Score"] = 0
        safe_df["Reasoning"]        = "GROQ_API_KEY not set."

    upsert_transactions(safe_df)

    # Save tally exports
    try:
        _save_tally_csv(safe_df, TALLY_CSV)
        _save_tally_xml(safe_df, TALLY_XML)
    except Exception as e:
        print(f"[Tally Export] Warning: {e}")

    # Generate insights markdown
    try:
        InsightsGenerator().generate_insights(INSIGHTS_PATH)
    except Exception:
        pass

    payload = _compute_metrics(safe_df)
    return json.loads(json.dumps(payload, cls=_SafeEncoder))


# ---------------------------------------------------------------------------
# API Views
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def upload_statement(request):
    """POST /api/upload/ — accepts PDF or image, runs pipeline, returns metrics."""
    if "file" not in request.FILES:
        return JsonResponse({"error": "No file provided."}, status=400)

    uploaded = request.FILES["file"]
    ext      = os.path.splitext(uploaded.name)[1].lower()
    allowed  = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}

    if ext not in allowed:
        return JsonResponse({"error": f"Unsupported file type '{ext}'."}, status=400)

    upload_dir = os.path.join("data", "input", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}{ext}")

    with open(save_path, "wb") as f:
        for chunk in uploaded.chunks():
            f.write(chunk)

    try:
        result = _run_pipeline(save_path)
        return JsonResponse(result, status=200)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)


@require_http_methods(["GET"])
def get_insights(request):
    """GET /api/insights/ — returns the financial_insights.md content."""
    path = os.path.join("data", "output", "financial_insights.md")
    if not os.path.exists(path):
        return JsonResponse({"available": False, "content": ""})
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return JsonResponse({"available": True, "content": content})


@require_http_methods(["GET"])
def download_tally_csv(request):
    """GET /api/download/tally-csv/ — serves tally_import.csv as download."""
    path = os.path.join("data", "output", "tally_import.csv")
    if not os.path.exists(path):
        return JsonResponse({"error": "File not yet generated. Upload a statement first."}, status=404)
    response = FileResponse(open(path, "rb"), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="tally_import.csv"'
    return response


@require_http_methods(["GET"])
def download_tally_xml(request):
    """GET /api/download/tally-xml/ — serves tally_import.xml as download."""
    path = os.path.join("data", "output", "tally_import.xml")
    if not os.path.exists(path):
        return JsonResponse({"error": "File not yet generated. Upload a statement first."}, status=404)
    response = FileResponse(open(path, "rb"), content_type="application/xml")
    response["Content-Disposition"] = 'attachment; filename="tally_import.xml"'
    return response


@require_http_methods(["GET"])
def get_status(request):
    """GET /api/status/ — health check."""
    return JsonResponse({"status": "ok", "service": "FinSight API"})
