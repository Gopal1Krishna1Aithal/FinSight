import os
import json
import pandas as pd
from typing import Dict, Any
from core.db.session import engine


class FrontendDataEngine:
    """
    Computes purely statistical and algorithmic metrics from the transaction
    history for the frontend dashboard to consume.
    Works seamlessly for both personal and business accounts.
    """

    def __init__(self):
        self.output_path = os.path.join("data", "output", "frontend_data.json")

    def generate(self) -> bool:
        try:
            df = pd.read_sql_query("SELECT * FROM transactions", engine)
            if df.empty:
                print(
                    "      [Data Engine] No transactions found. Skipping frontend JSON."
                )
                return False

            df["date"] = pd.to_datetime(df["date"])

            # Cleanly sort by date
            df = df.sort_values(by="date").reset_index(drop=True)

            # Compute independent metrics
            runway_data = self._compute_runway_and_burn(df)
            vendor_data = self._compute_vendor_dependency(df)
            subs_data = self._compute_subscriptions(df)
            crisis_data = self._compute_crisis_survival(df)
            cash_data = self._compute_cash_withdrawal_limit(df)
            pnl_data = self._compute_draft_pnl(df)
            
            # New metrics for multi-period display
            monthly_trends = self._compute_monthly_trends(df)
            period_breakdown = self._compute_period_breakdown(df)

            # Assemble God-mode JSON for the frontend
            payload: Dict[str, Any] = {
                "runway_and_burn_rate": runway_data,
                "crisis_survival_mode": crisis_data,
                "cash_withdrawal_tracker": cash_data,
                "draft_pnl_statement": pnl_data,
                "vendor_dependency": vendor_data,
                "recurring_subscriptions": subs_data,
                "monthly_trends": monthly_trends,
                "period_breakdown": period_breakdown,
                "summary": {
                    "total_transactions": int(len(df)),
                    "latest_balance": float(df.iloc[-1]["balance"]),
                    "date_range": {
                        "start": df.iloc[0]["date"].strftime("%Y-%m-%d"),
                        "end": df.iloc[-1]["date"].strftime("%Y-%m-%d"),
                    },
                },
            }

            class _NumpySafe(json.JSONEncoder):
                def default(self, obj):
                    import numpy as np
                    if isinstance(obj, np.bool_): return bool(obj)
                    if isinstance(obj, np.integer): return int(obj)
                    if isinstance(obj, np.floating): return float(obj)
                    return super().default(obj)

            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, cls=_NumpySafe)

            print(f"      ✅  Frontend APIs → {self.output_path}")
            return True

        except Exception as e:
            print(f"      [Data Engine] Failed to generate frontend JSON: {e}")
            return False

    def _compute_runway_and_burn(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty: return {}
        total_outflow = df["debit"].sum()
        total_inflow = df["credit"].sum()
        current_balance = df.iloc[-1]["balance"]
        days_diff = (df["date"].max() - df["date"].min()).days
        days_diff = max(1, days_diff)
        daily_burn = total_outflow / days_diff
        monthly_burn = daily_burn * 30
        runway_days = float(current_balance / daily_burn) if daily_burn > 0 else 9999.0
        return {
            "daily_burn_rate": round(daily_burn, 2),
            "monthly_burn_rate": round(monthly_burn, 2),
            "average_monthly_inflow": round((total_inflow / days_diff) * 30, 2),
            "current_balance": round(current_balance, 2),
            "runway_days_left": round(runway_days, 1),
            "health_status": "CRITICAL" if runway_days < 30 else ("WARNING" if runway_days < 90 else "HEALTHY"),
        }

    def _compute_monthly_trends(self, df: pd.DataFrame) -> list:
        df = df.copy()
        df["_period"] = df["date"].dt.to_period("M")
        monthly = (
            df.groupby("_period")
            .agg(inflow=("credit", "sum"), outflow=("debit", "sum"))
            .reset_index()
        )
        monthly["net"] = monthly["inflow"] - monthly["outflow"]
        monthly["month"] = monthly["_period"].dt.strftime("%b %Y")
        return [
            {
                "month": row["month"],
                "inflow": round(float(row["inflow"]), 2),
                "outflow": round(float(row["outflow"]), 2),
                "net": round(float(row["net"]), 2),
            }
            for _, row in monthly.iterrows()
        ]

    def _compute_period_breakdown(self, df: pd.DataFrame) -> list:
        if "period_label" not in df.columns:
            return []
        
        periods = []
        for label in df["period_label"].unique():
            pdf = df[df["period_label"] == label]
            periods.append({
                "label": str(label),
                "date_range": {
                    "start": pdf["date"].min().strftime("%Y-%m-%d"),
                    "end": pdf["date"].max().strftime("%Y-%m-%d"),
                },
                "total_inflow": round(float(pdf["credit"].sum()), 2),
                "total_outflow": round(float(pdf["debit"].sum()), 2),
                "net_cashflow": round(float(pdf["credit"].sum() - pdf["debit"].sum()), 2),
                "closing_balance": round(float(pdf.iloc[-1]["balance"]), 2),
            })
        return periods

    def _compute_vendor_dependency(self, df: pd.DataFrame) -> Dict[str, Any]:
        outflows = df[df["debit"] > 0].copy()
        if outflows.empty: return {"top_vendors": []}
        total_outflow = outflows["debit"].sum()
        vendor_group = outflows.groupby("clean_description")["debit"].agg(["sum", "count"]).reset_index()
        vendor_group = vendor_group.sort_values(by="sum", ascending=False)
        top_vendors = []
        for _, row in vendor_group.head(10).iterrows():
            pct = (row["sum"] / total_outflow) * 100
            top_vendors.append({
                "vendor_name": str(row["clean_description"]),
                "total_spend": round(float(row["sum"]), 2),
                "transaction_count": int(row["count"]),
                "percentage_of_total_outflow": round(float(pct), 2),
            })
        return {"total_tracked_vendors": len(vendor_group), "top_vendors": top_vendors}

    def _compute_subscriptions(self, df: pd.DataFrame) -> Dict[str, Any]:
        outflows = df[df["debit"] > 0].copy()
        if outflows.empty: return {"detected_subscriptions": []}
        subs = outflows.groupby(["clean_description", "debit"]).size().reset_index(name="count")
        recurring = subs[subs["count"] >= 2].sort_values(by="debit", ascending=False)
        detected_subs = []
        total_monthly_est = 0.0
        for _, row in recurring.iterrows():
            vendor = row["clean_description"]
            amt = row["debit"]
            if any(x in vendor.upper() for x in ["ATM WITHDRAWAL", "CASH DEPOSIT", "UPI TRANSFER"]):
                continue
            detected_subs.append({
                "vendor_name": str(vendor),
                "recurring_amount": round(float(amt), 2),
                "times_detected": int(row["count"]),
            })
            total_monthly_est += float(amt)
        return {
            "total_recurring_subscriptions_found": len(detected_subs),
            "estimated_fixed_monthly_cost": round(total_monthly_est, 2),
            "detected_subscriptions": detected_subs,
        }

    def _compute_crisis_survival(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty: return {}
        ess_cats = ["Payroll", "Healthcare & Medical", "Utilities & Telecom", "Software & IT", "Bank Charges & Fees", "Credit Card Repayment", "Loan & EMI"]
        ess_df = df[(df["debit"] > 0) & (df["coa_category"].isin(ess_cats))]
        total_ess = ess_df["debit"].sum()
        curr_bal = df.iloc[-1]["balance"]
        days_diff = max(1, (df["date"].max() - df["date"].min()).days)
        daily_crisis_burn = total_ess / days_diff
        crisis_runway = float(curr_bal / daily_crisis_burn) if daily_crisis_burn > 0 else 9999.0
        return {
            "essential_monthly_overhead": round(daily_crisis_burn * 30, 2),
            "crisis_runway_days_left": round(crisis_runway, 1),
            "total_tracked_essential_spend": round(total_ess, 2),
        }

    def _compute_cash_withdrawal_limit(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty: return {}
        cash_df = df[(df["debit"] > 0) & (df["coa_category"] == "ATM Withdrawal")]
        total_cash = cash_df["debit"].sum()
        limit = 2000000.0
        return {
            "total_cash_withdrawn": round(total_cash, 2),
            "tds_194N_limit": limit,
            "limit_remaining": round(max(0.0, limit - total_cash), 2),
            "warning_active": total_cash >= limit,
        }

    def _compute_draft_pnl(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty: return {}
        contras = ["Fund Transfer", "Cash Deposit", "Credit Card Repayment", "Loan & EMI"]
        inc_df = df[(df["credit"] > 0) & (~df["coa_category"].isin(contras))]
        opex_cats = ["Payroll", "Fuel & Auto", "Healthcare & Medical", "Utilities & Telecom", "Software & IT", "UPI & Digital Payment", "E-Commerce & Retail", "Travel & Transport", "IMPS Transfer"]
        opex_df = df[(df["debit"] > 0) & (df["coa_category"].isin(opex_cats))]
        fin_df = df[(df["debit"] > 0) & (df["coa_category"] == "Bank Charges & Fees")]
        net_profit = inc_df["credit"].sum() - (opex_df["debit"].sum() + fin_df["debit"].sum())
        return {
            "Total_Income": round(inc_df["credit"].sum(), 2),
            "Operating_Expenses": round(opex_df["debit"].sum(), 2),
            "Financial_Expenses": round(fin_df["debit"].sum(), 2),
            "Gross_Estimated_Profit": round(net_profit, 2),
            "Non_PnL_Outflows": {
                "Cash_Drawings": round(df[(df["debit"] > 0) & (df["coa_category"] == "ATM Withdrawal")]["debit"].sum(), 2),
                "Suspense_Uncategorized": round(df[(df["debit"] > 0) & (df["coa_category"] == "Uncategorized")]["debit"].sum(), 2),
            },
        }
