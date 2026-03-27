import os
import pandas as pd
from typing import Optional
from groq import Groq
from core.db.session import engine

class ChatService:
    """
    Provides a contextual chat interface for financial queries.
    Summarizes the DB state before asking the LLM for an answer.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found. Please check your .env file or environment variables.")
        self.client = Groq(api_key=self.api_key)

    def ask(self, user_query: str) -> str:
        """
        Retrieves current context, constructs a prompt, and returns the AI answer.
        """
        try:
            # 1. Get Summary Context
            df = pd.read_sql_query("SELECT * FROM transactions", engine)
            if df.empty:
                return "The statement database is currently empty. Please upload a statement first."

            df["date"] = pd.to_datetime(df["date"])
            total_in  = df["credit"].sum()
            total_out = df["debit"].sum()
            balance   = df.sort_values("date").iloc[-1]["balance"]
            
            # Monthly summary
            df["month"] = df["date"].dt.strftime("%b %Y")
            monthly = df.groupby("month").agg({"credit":"sum", "debit":"sum"}).to_dict('index')
            monthly_str = "\n".join([f"- {m}: In ₹{v['credit']:,.0f}, Out ₹{v['debit']:,.0f}" for m,v in monthly.items()])
            
            # Top vendors
            vendors = df[df["debit"]>0].groupby("clean_description")["debit"].sum().sort_values(ascending=False).head(5)
            vendor_str = "\n".join([f"- {v}: ₹{amt:,.0f}" for v, amt in vendors.items()])

            # Burn Rate / Runway
            days = max(1, (df["date"].max() - df["date"].min()).days)
            daily_burn = total_out / days
            runway = (balance / daily_burn) if daily_burn > 0 else 999
            
            # 2. Build Prompt
            prompt = f"""You are FinSight AI, a financial assistant. Use the following context from the user's uploaded bank statements to answer their question.
Be direct, professional, and helpful. Use Rupee (₹) for currency.

### BUSINESS CONTEXT:
- Total Inflow: ₹{total_in:,.2f}
- Total Outflow: ₹{total_out:,.2f}
- Current Balance: ₹{balance:,.2f}
- Daily Burn Rate: ₹{daily_burn:,.2f}
- Est. Cash Runway: {runway:.1f} days
- Date Range: {df["date"].min().date()} to {df["date"].max().date()}

### MONTHLY TRENDS:
{monthly_str}

### TOP VENDORS:
{vendor_str}

### USER QUESTION:
{user_query}

AI Response:"""

            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return f"I encountered an error while analyzing your data: {str(e)}"
