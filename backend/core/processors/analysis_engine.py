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

            # Assemble God-mode JSON for the frontend
            payload: Dict[str, Any] = {
                "runway_and_burn_rate": runway_data,
                "crisis_survival_mode": crisis_data,
                "cash_withdrawal_tracker": cash_data,
                "draft_pnl_statement": pnl_data,
                "vendor_dependency": vendor_data,
                "recurring_subscriptions": subs_data,
                "summary": {
                    "total_transactions": int(len(df)),
                    "latest_balance": float(df.iloc[-1]["balance"]),
                    "date_range": {
                        "start": df.iloc[0]["date"].strftime("%Y-%m-%d"),
                        "end": df.iloc[-1]["date"].strftime("%Y-%m-%d"),
                    },
                },
            }

            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)

            print(f"      ✅  Frontend APIs → {self.output_path}")
            return True

        except Exception as e:
            print(f"      [Data Engine] Failed to generate frontend JSON: {e}")
            return False

    def _compute_runway_and_burn(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculates daily burn rate and cash runway based on historical spend.
        For personal accounts: How long current savings will last at current spending.
        For business accounts: How long cash reserves will last.
        """
        if df.empty:
            return {}

        total_outflow = df["debit"].sum()
        total_inflow = df["credit"].sum()
        current_balance = df.iloc[-1]["balance"]

        days_difference = (df["date"].max() - df["date"].min()).days
        days_difference = max(1, days_difference)  # prevent division by zero

        daily_burn_rate = total_outflow / days_difference
        monthly_burn_rate = daily_burn_rate * 30

        # Calculate runaway (in days) based on current balance and daily burn
        runway_days = (
            float(current_balance / daily_burn_rate) if daily_burn_rate > 0 else 9999.0
        )

        return {
            "daily_burn_rate": round(daily_burn_rate, 2),
            "monthly_burn_rate": round(monthly_burn_rate, 2),
            "average_monthly_inflow": round((total_inflow / days_difference) * 30, 2),
            "current_balance": round(current_balance, 2),
            "runway_days_left": round(runway_days, 1),
            "health_status": (
                "CRITICAL"
                if runway_days < 30
                else ("WARNING" if runway_days < 90 else "HEALTHY")
            ),
        }

    def _compute_vendor_dependency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Profiles exactly where the money goes by grouping Clean_Description.
        Identifies highest external dependencies.
        """
        outflows = df[df["debit"] > 0].copy()
        if outflows.empty:
            return {"top_vendors": []}

        total_outflow = outflows["debit"].sum()

        # Eliminate bank fees and internal transfers from dependency profiling if possible
        # Actually, let's keep it raw. Clean_Description handles this mostly.

        vendor_group = (
            outflows.groupby("clean_description")["debit"]
            .agg(["sum", "count"])
            .reset_index()
        )
        vendor_group = vendor_group.sort_values(by="sum", ascending=False)

        top_vendors = []
        for _, row in vendor_group.head(10).iterrows():
            pct = (row["sum"] / total_outflow) * 100
            top_vendors.append(
                {
                    "vendor_name": str(row["clean_description"]),
                    "total_spend": round(float(row["sum"]), 2),
                    "transaction_count": int(row["count"]),
                    "percentage_of_total_outflow": round(float(pct), 2),
                }
            )

        return {"total_tracked_vendors": len(vendor_group), "top_vendors": top_vendors}

    def _compute_subscriptions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Identifies recurring outflows grouping by identical vendor and identical/similar amounts
        occurring multiple times.
        """
        outflows = df[df["debit"] > 0].copy()
        if outflows.empty:
            return {"detected_subscriptions": []}

        # Simplistic subscription detection:
        # Group by vendor and the exact debit amount.
        # If it happens 2+ times, we flag it as a recurring payment.

        subs = (
            outflows.groupby(["clean_description", "debit"])
            .size()
            .reset_index(name="count")
        )

        # Filter for recurring
        recurring = subs[subs["count"] >= 2].sort_values(by="debit", ascending=False)

        detected_subs = []
        total_monthly_est = 0.0

        for _, row in recurring.iterrows():
            vendor = row["clean_description"]
            amt = row["debit"]
            freq = row["count"]

            # To be safer, we can filter out common noise like 'ATM WITHDRAWAL'
            # if someone withdraws 5000 twice, it's not a subscription
            if (
                "ATM WITHDRAWAL" in vendor.upper()
                or "CASH DEPOSIT" in vendor.upper()
                or "UPI TRANSFER" in vendor.upper()
            ):
                continue

            detected_subs.append(
                {
                    "vendor_name": str(vendor),
                    "recurring_amount": round(float(amt), 2),
                    "times_detected": int(freq),
                }
            )
            total_monthly_est += float(amt)  # A rough estimate of monthly fixed cost

        return {
            "total_recurring_subscriptions_found": len(detected_subs),
            "estimated_fixed_monthly_cost": round(total_monthly_est, 2),
            "detected_subscriptions": detected_subs,
        }

    def _compute_crisis_survival(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculates the 'Crisis Mode' runway by stripping out non-essential variable costs.
        """
        if df.empty:
            return {}

        essential_categories = [
            "Payroll",
            "Healthcare & Medical",
            "Utilities & Telecom",
            "Software & IT",
            "Bank Charges & Fees",
            "Credit Card Repayment",
            "Loan & EMI",
        ]

        # Filter strictly for essential debits
        essential_df = df[
            (df["debit"] > 0) & (df["coa_category"].isin(essential_categories))
        ]

        total_essential_outflow = essential_df["debit"].sum()
        current_balance = df.iloc[-1]["balance"]

        days_difference = (df["date"].max() - df["date"].min()).days
        days_difference = max(1, days_difference)

        daily_crisis_burn_rate = total_essential_outflow / days_difference
        monthly_crisis_burn_rate = daily_crisis_burn_rate * 30

        crisis_runway_days = (
            float(current_balance / daily_crisis_burn_rate)
            if daily_crisis_burn_rate > 0
            else 9999.0
        )

        return {
            "essential_monthly_overhead": round(monthly_crisis_burn_rate, 2),
            "crisis_runway_days_left": round(crisis_runway_days, 1),
            "total_tracked_essential_spend": round(total_essential_outflow, 2),
        }

    def _compute_cash_withdrawal_limit(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculates total cash withdrawn (Section 194N TDS tracking).
        """
        if df.empty:
            return {}

        # Sum of debits where category is ATM Withdrawal
        cash_df = df[(df["debit"] > 0) & (df["coa_category"] == "ATM Withdrawal")]
        total_cash_withdrawn = cash_df["debit"].sum()

        limit_20l = 2000000.0
        remaining = max(0.0, limit_20l - total_cash_withdrawn)

        return {
            "total_cash_withdrawn": round(total_cash_withdrawn, 2),
            "tds_194N_limit": limit_20l,
            "limit_remaining": round(remaining, 2),
            "warning_active": total_cash_withdrawn >= limit_20l,
        }

    def _compute_draft_pnl(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Groups everything into a standard Draft Profit & Loss statement format.
        """
        if df.empty:
            return {}

        # 1. Income (All credits excluding internal contras)
        contras = [
            "Fund Transfer",
            "Cash Deposit",
            "Credit Card Repayment",
            "Loan & EMI",
        ]
        income_df = df[(df["credit"] > 0) & (~df["coa_category"].isin(contras))]
        total_income = income_df["credit"].sum()

        # 2. Operating Expenses
        opex_cats = [
            "Payroll",
            "Fuel & Auto",
            "Healthcare & Medical",
            "Utilities & Telecom",
            "Software & IT",
            "UPI & Digital Payment",
            "E-Commerce & Retail",
            "Travel & Transport",
            "IMPS Transfer",
        ]
        opex_df = df[(df["debit"] > 0) & (df["coa_category"].isin(opex_cats))]
        total_opex = opex_df["debit"].sum()

        # 3. Financial Expenses
        finance_cats = ["Bank Charges & Fees"]
        finance_df = df[(df["debit"] > 0) & (df["coa_category"].isin(finance_cats))]
        total_finance = finance_df["debit"].sum()

        # 4. Cash Drawings & Suspense
        drawings_df = df[(df["debit"] > 0) & (df["coa_category"] == "ATM Withdrawal")]
        total_drawings = drawings_df["debit"].sum()

        suspense_df = df[(df["debit"] > 0) & (df["coa_category"] == "Uncategorized")]
        total_suspense = suspense_df["debit"].sum()

        net_profit = total_income - (total_opex + total_finance)

        return {
            "Total_Income": round(total_income, 2),
            "Operating_Expenses": round(total_opex, 2),
            "Financial_Expenses": round(total_finance, 2),
            "Gross_Estimated_Profit": round(net_profit, 2),
            "Non_PnL_Outflows": {
                "Cash_Drawings": round(total_drawings, 2),
                "Suspense_Uncategorized": round(total_suspense, 2),
            },
        }
