import os
import sys
import json
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom
import math
import numpy as np

from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from dotenv import load_dotenv

# 1. Environment and Base imports
load_dotenv()

# Global cache for lazy imports to prevent repeated stall
_LAZY_CACHE = {}

def _get_pipeline_deps():
    if not _LAZY_CACHE:
        print("      → Warming up AI & Data engines for the first time...")
        
        print("        [1/8] Loading pandas...")
        import pandas as pd
        
        print("        [2/8] Loading HDFCPDFExtractor...")
        from core.extractors.hdfc_pdf import HDFCPDFExtractor
        
        print("        [3/8] Loading HDFCDataCleaner...")
        from core.processors.cleaner import HDFCDataCleaner
        
        print("        [4/8] Loading DataSanitizer...")
        from core.processors.sanitizer import DataSanitizer
        
        print("        [5/8] Loading CoAMapper...")
        from core.ai_services.coa_mapper import CoAMapper
        
        print("        [6/8] Loading DB Session...")
        from core.db.session import init_db
        
        print("        [7/8] Loading DB Ops...")
        from core.db.operations import upsert_transactions
        
        print("        [8/8] Loading InsightsGenerator...")
        from core.ai_services.insights_generator import InsightsGenerator
        
        _LAZY_CACHE.update({
            "pd": pd,
            "HDFCPDFExtractor": HDFCPDFExtractor,
            "HDFCDataCleaner": HDFCDataCleaner,
            "DataSanitizer": DataSanitizer,
            "CoAMapper": CoAMapper,
            "init_db": init_db,
            "upsert_transactions": upsert_transactions,
            "InsightsGenerator": InsightsGenerator
        })
        print("      ✅  Engines ready.")
    return _LAZY_CACHE


class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.bool_):   return bool(obj)
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        return super().default(obj)

def _sanitize_data(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_data(v) for v in obj]
    elif isinstance(obj, (float, np.floating)):
        if not math.isfinite(obj):
            return None
    return obj


# ---------------------------------------------------------------------------
# Tally export helpers (mirrored from main.py so the API can save them too)
# ---------------------------------------------------------------------------

def _save_tally_csv(df, path: str) -> None:
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

def _validate_ledger_math(df):
    df = df.sort_values(["Period", "Date"]).reset_index(drop=True)
    df["Math_Audit_Status"] = "VERIFIED"
    df["Math_Error_Flag"] = False

    for i in range(1, len(df)):
        # We only check math if the previous row belongs to the same bank statement period
        if df.loc[i, "Period"] == df.loc[i-1, "Period"]:
            prev_bal = float(df.loc[i-1, "Balance"])
            curr_dr  = float(df.loc[i, "Debit"])
            curr_cr  = float(df.loc[i, "Credit"])
            curr_bal = float(df.loc[i, "Balance"])
            
            # Allow for tiny rounding differences (floating point math)
            expected_bal = round(prev_bal - curr_dr + curr_cr, 2)
            actual_bal   = round(curr_bal, 2)
            
            if abs(expected_bal - actual_bal) > 0.02:
                df.at[i, "Math_Audit_Status"] = "ERROR_DETECTION_ACTIVE"
                df.at[i, "Math_Error_Flag"] = True
                print(f"      [Integrity Check] 🚩 Math Mismatch at row {i}: Expected {expected_bal}, Found {actual_bal}")
    
    return df


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

    # ── Category breakdown (Expenses only) ──────────────────────────────────
    expenses_only = df[df["Debit"] > 0]
    cat_expenses = (
        expenses_only.groupby("CoA_Category")["Debit"]
        .agg(["sum", "count"]).reset_index()
        .sort_values("sum", ascending=False)
    )
    category_breakdown = [
        {
            "category": str(row["CoA_Category"]),
            "value":    round(float(row["sum"]), 2),
            "count":    int(row["count"]),
        }
        for _, row in cat_expenses.iterrows()
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
        "category_breakdown": category_breakdown,
        "transactions": [
            {
                "Date": row["Date"].strftime("%Y-%m-%d") if hasattr(row["Date"], "strftime") else str(row["Date"]),
                "Clean_Description": str(row["Clean_Description"]),
                "CoA_Category": str(row["CoA_Category"]),
                "Debit": float(row["Debit"]),
                "Credit": float(row["Credit"]),
                "Balance": float(row["Balance"]),
                "Math_Error": bool(row.get("Math_Error_Flag", False)),
                "Audit_Status": str(row.get("Math_Audit_Status", "UNAUDITED"))
            }
            for _, row in df.sort_values(["Date"], ascending=False).iterrows()
        ],
    }


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

# ── Multi-period helpers (mirrored from main.py) ───────────────────────────
_QUARTER_LABELS = {"Q1": "Apr–Jun", "Q2": "Jul–Sep", "Q3": "Oct–Dec", "Q4": "Jan–Mar"}
_FY_LABELS      = {"FY2324": "23", "FY2425": "24", "FY2526": "25"}

def _infer_period_label(filename: str, df) -> tuple[str, str]:
    import re
    stem = os.path.basename(filename)
    m = re.search(r"(Q[1-4])[\s_-]*(FY\d{4})", stem, re.IGNORECASE)
    if m:
        q = m.group(1).upper(); fy = m.group(2).upper()
        qm = _QUARTER_LABELS.get(q, "?"); yy = _FY_LABELS.get(fy, fy[-2:])
        return f"{q} {fy}", f"{q} {qm} {yy}"
    if df is not None and not df.empty and "Date" in df.columns:
        d_min = df["Date"].min().strftime("%b %Y")
        d_max = df["Date"].max().strftime("%b %Y")
        return f"{d_min}–{d_max}", f"{d_min}–{d_max}"[:18]
    return "FY2324", "Transactions"


def _run_pipeline(file_paths: list[str]) -> dict:
    """
    Orchestrates the multi-stage extraction and processing pipeline.
    Uses lazy-loading to ensure the server stays responsive on first run.
    """
    print(f"\n[1/5] Ingesting {len(file_paths)} statement(s)...")
    deps = _get_pipeline_deps()
    
    OUT_DIR       = os.path.join("data", "output")
    INSIGHTS_PATH = os.path.join(OUT_DIR, "financial_insights.md")
    TALLY_CSV     = os.path.join(OUT_DIR, "tally_export_v1.csv")
    TALLY_XML     = os.path.join(OUT_DIR, "tally_export_v1.xml")
    os.makedirs(OUT_DIR, exist_ok=True)

    groq_api_key = os.getenv("GROQ_API_KEY")
    all_dfs = []

    for f_path in file_paths:
        fname = os.path.basename(f_path)
        print(f"      → Processing: {fname}")
        
        # Extract
        if f_path.lower().endswith(".pdf"):
            print(f"        [Extractor] Running HDFCPDFExtractor...")
            raw_data = deps["HDFCPDFExtractor"](f_path).extract() or []
        else:
            print(f"        [Extractor] Running ImageOCRExtractor...")
            from core.extractors.image_ocr import ImageOCRExtractor
            raw_data = ImageOCRExtractor(image_paths=[f_path]).extract() or []
        
        if not raw_data: 
            print(f"        [!] No data extracted for {fname}.")
            continue
        print(f"        [Extractor] Done. Found {len(raw_data)} raw rows.")

        # Clean + Sanitize
        print(f"        [Processor] Cleaning & Sanitizing...")
        clean_df = deps["HDFCDataCleaner"](raw_data).clean()
        if clean_df.empty: 
            print(f"        [!] Cleaning resulted in 0 rows.")
            continue
        safe_df = deps["DataSanitizer"](clean_df).scrub_pii()

        # CoA Mapping
        if groq_api_key:
            print(f"        [AI] Mapping to Chart of Accounts (Groq)...")
            safe_df = deps["CoAMapper"](api_key=groq_api_key).map(safe_df)
        else:
            print(f"        [AI] Skipping CoA Mapping (No API Key).")
            safe_df["CoA_Category"] = "Uncategorized"; safe_df["Confidence_Score"] = 0; safe_df["Reasoning"] = "No API Key"

        # Tag period
        period_label, _ = _infer_period_label(fname, safe_df)
        safe_df["Period"] = period_label
        
        # Upsert
        print(f"        [DB] Updating database...")
        deps["upsert_transactions"](safe_df, source_file=fname, period_label=period_label)
        all_dfs.append(safe_df)

    if not all_dfs:
        return {"error": "Extraction failed for all files. Check formats or bank layout."}

    combined_df = deps["pd"].concat(all_dfs, ignore_index=True)
    combined_df = combined_df.sort_values(["Period", "Date"]).reset_index(drop=True)

    # ── Deterministic Integrity Audit ───────────
    print("\n[2/5] Performing mathematical integrity audit...")
    combined_df = _validate_ledger_math(combined_df)

    # Save tally exports
    print("[3/5] Generating Tally export formats (CSV/XML)...")
    try:
        _save_tally_csv(combined_df, TALLY_CSV)
        _save_tally_xml(combined_df, TALLY_XML)
    except Exception as e: print(f"      [Tally Export] Warning: {e}")

    # Generate insights
    print("[4/5] Synthesizing professional financial insights (Groq)...")
    try: deps["InsightsGenerator"]().generate_insights(INSIGHTS_PATH, df=combined_df)
    except Exception as e: print(f"      [Insights] Error: {e}")

    # Compute metrics + period breakdown
    print("[5/5] Compiling final dashboard metrics...")
    payload = _compute_metrics(combined_df)
    
    # Add period_breakdown for multi-period display
    periods = []
    for label in combined_df["Period"].unique():
        pdf = combined_df[combined_df["Period"] == label]
        periods.append({
            "label":           str(label),
            "total_inflow":    round(float(pdf["Credit"].sum()), 2),
            "total_outflow":   round(float(pdf["Debit"].sum()), 2),
            "net_cashflow":    round(float(pdf["Credit"].sum() - pdf["Debit"].sum()), 2),
            "closing_balance": round(float(pdf.iloc[-1]["Balance"]), 2),
        })
    payload["period_breakdown"] = periods

    # Sanitize and encode for JSON safety
    sanitized = _sanitize_data(payload)
    return json.loads(json.dumps(sanitized, cls=_SafeEncoder))


# ---------------------------------------------------------------------------
# API Views
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def upload_statement(request):
    """POST /api/upload/ — accepts multiple files, runs batch pipeline, returns metrics."""
    print("\n[DEBUG] upload_statement endpoint triggered.")
    if "file" not in request.FILES:
        return JsonResponse({"error": "No file provided."}, status=400)

    uploaded_files = request.FILES.getlist("file")
    allowed_exts   = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}
    upload_dir     = os.path.join("data", "input", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    saved_paths = []
    
    for up_file in uploaded_files:
        ext = os.path.splitext(up_file.name)[1].lower()
        if ext not in allowed_exts:
            continue # skip invalid but keep processing others
            
        save_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{up_file.name}")
        with open(save_path, "wb") as f:
            for chunk in up_file.chunks():
                f.write(chunk)
        saved_paths.append(save_path)

    if not saved_paths:
        return JsonResponse({"error": "No supported files found in upload."}, status=400)

    try:
        result = _run_pipeline(saved_paths)
        return JsonResponse(result, status=200)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        for p in saved_paths:
            if os.path.exists(p): os.remove(p)


@csrf_exempt
@require_http_methods(["POST"])
def chat_query(request):
    """POST /api/chat/ — accepts { "message": "..." } and returns an AI answer."""
    import json
    try:
        data = json.loads(request.body)
        user_msg = data.get("message", "").strip()
        if not user_msg:
            return JsonResponse({"error": "No message provided."}, status=400)
        
        from core.ai_services.chat_service import ChatService
        ai_resp = ChatService().ask(user_msg)
        return JsonResponse({"response": ai_resp}, status=200)
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


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
def download_excel(request):
    """GET /api/download/excel/ — serves the clean_statement.xlsx workbook."""
    path = os.path.join("data", "output", "clean_statement.xlsx")
    if not os.path.exists(path):
        return JsonResponse({"error": "Excel file not yet generated. Run the pipeline first."}, status=404)
    response = FileResponse(
        open(path, "rb"),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="clean_statement.xlsx"'
    return response


@require_http_methods(["GET"])
def get_dashboard(request):
    """GET /api/dashboard/ — aggregates all database transactions into a dashboard payload."""
    from core.db.session import engine
    import pandas as pd
    
    try:
        df = pd.read_sql_query("SELECT * FROM transactions", engine)
        if df.empty:
            return JsonResponse({"error": "No data in database. Upload a statement first."}, status=404)
        
        # Format for _compute_metrics: Needs 'Date', 'Debit', 'Credit', 'Balance', 'CoA_Category' (case matches)
        df["Date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={
            "debit":             "Debit",
            "credit":            "Credit",
            "balance":           "Balance",
            "coa_category":      "CoA_Category",
            "clean_description": "Clean_Description",
        })
        
        # Period computation for period_breakdown
        payload = _compute_metrics(df)
        
        if "period_label" in df.columns:
            periods = []
            for label in df["period_label"].unique():
                pdf = df[df["period_label"] == label]
                periods.append({
                    "label":           str(label),
                    "total_inflow":    round(float(pdf["Credit"].sum()), 2),
                    "total_outflow":   round(float(pdf["Debit"].sum()), 2),
                    "net_cashflow":    round(float(pdf["Credit"].sum() - pdf["Debit"].sum()), 2),
                    "closing_balance": round(float(pdf.iloc[-1]["Balance"]), 2),
                })
            payload["period_breakdown"] = periods
            
        return JsonResponse(payload, status=200, encoder=_SafeEncoder)
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def get_status(request):
    """GET /api/status/ — health check."""
    return JsonResponse({"status": "ok", "service": "FinSight API"})
