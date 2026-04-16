import os
from typing import Optional
from core.db.session import SessionLocal, get_engine
from core.db.models import Transaction


class InsightsGenerator:
    """
    Queries the central transaction database and generates financial
    insights using the Groq LLM.
    """

    def __init__(self, api_key: Optional[str] = None):
        from groq import Groq
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment for InsightsGenerator."
            )
        self.client = Groq(api_key=self.api_key)

    def generate_insights(
        self, output_path: str, df: Optional[object] = None
    ) -> bool:
        import pandas as pd
        """
        Reads transactions, aggregates them, and asks the LLM
        for business insights. Saves the result to a markdown file.
        Returns True on success.
        """
        if df is None:
            # Fallback to historic data if no specific dataframe passed
            engine = get_engine()
            query = "SELECT * FROM transactions"
            try:
                df = pd.read_sql_query(query, engine)
            except Exception as e:
                print(f"      [Insights] Error reading from DB: {e}")
                return False

        if df.empty:
            print("      [Insights] Dataframe is empty, skipping insights.")
            return False

        print(f"      [Insights] Analyzing {len(df)} transactions for the report...")

        # Ensure we work on a copy so we don't modify the original dataframe's columns
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        # Ensure date type
        df["date"] = pd.to_datetime(df["date"])

        # Calculate summaries
        total_inflow = df["credit"].sum()
        total_outflow = df["debit"].sum()
        current_balance = (
            df.sort_values("date").iloc[-1]["balance"] if not df.empty else 0.0
        )

        # Breakdown by all categories
        expenses = df[df["debit"] > 0]
        incomes = df[df["credit"] > 0]

        expense_cats = (
            expenses.groupby("coa_category")["debit"].sum().sort_values(ascending=False)
        )
        income_cats = (
            incomes.groupby("coa_category")["credit"].sum().sort_values(ascending=False)
        )

        expense_str = (
            "\n".join(
                [
                    f"- {cat}: ₹{amt:,.2f} ({(amt/total_outflow)*100:.1f}%)"
                    for cat, amt in expense_cats.items()
                ]
            )
            if total_outflow
            else "None"
        )
        income_str = (
            "\n".join(
                [
                    f"- {cat}: ₹{amt:,.2f} ({(amt/total_inflow)*100:.1f}%)"
                    for cat, amt in income_cats.items()
                ]
            )
            if total_inflow
            else "None"
        )

        # Largest single transaction
        max_debit_row = (
            expenses.loc[expenses["debit"].idxmax()] if not expenses.empty else None
        )
        largest_expense = (
            f"₹{max_debit_row['debit']:,.2f} ({max_debit_row['coa_category']} - {max_debit_row['clean_description']})"
            if max_debit_row is not None
            else "None"
        )

        # Monthly Trends
        df_sorted = df.sort_values("date")
        df_sorted["month"] = df_sorted["date"].dt.strftime("%B %Y")
        monthly_str = ""
        for month, group in df_sorted.groupby("month", sort=False):
            m_in = group["credit"].sum()
            m_out = group["debit"].sum()
            monthly_str += f"- {month}: Inflow ₹{m_in:,.2f} | Outflow ₹{m_out:,.2f} | Net ₹{(m_in - m_out):,.2f}\n"

        # Format stats into a prompt context
        prompt = f"""You are an elite, perceptive financial analyst advising a small to medium Indian business.
Based on the historic bank transactions of the company, provide a highly readable, analytical, 
and professional financial summary and insights report in Markdown format. Go beyond just repeating the numbers.

### Key Metrics:
- Total Inflow (Credits): ₹{total_inflow:,.2f}
- Total Outflow (Debits): ₹{total_outflow:,.2f}
- Net Cash Flow: ₹{(total_inflow - total_outflow):,.2f}
- Latest Known Balance: ₹{current_balance:,.2f}
- Largest Single Expense: {largest_expense}

### Monthly Breakdown:
{monthly_str}

### Income Breakdown:
{income_str}

### Expense Breakdown (Chart of Accounts):
{expense_str}

Please generate a structured report including:
1. **Executive Summary**: A brief, high-level overview of the financial health and cash flow trajectory.
2. **Cash Flow & Monthly Trends**: Analyze the inflow vs outflow, the month-over-month trajectory, and any drastic spikes or dips in specific months.
3. **Key Spending & Behavioral Patterns**: 
   - Focus on the largest percentage expenses. 
   - State whether the proportions seem healthy for a typical small business.
   - Look closely at "Uncategorized" or "ATM Withdrawal" lines. High ATM usage often points to untracked cash leakage — flag this if it's unusually high (e.g. >10% of total expenses).
4. **Actionable Recommendations**: 3-4 highly specific, immediate actions the business owner can take to improve margins, track cash better, or handle debt.

Style Guidelines:
- Use bullet points, bold text for key figures, and tables if useful.
- Provide strategic, advisory tone rather than purely descriptive.
- Keep it direct and actionable. 
- Do not output anything outside of the Markdown report.
"""
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Low temp for analytical text
                max_tokens=1500,
            )
            report = response.choices[0].message.content.strip()

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)

            print(f"      ✅  Insights → {output_path}")
            return True
        except Exception as e:
            print(f"      [Insights] Error generating report: {e}")
            return False
