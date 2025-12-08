from fastapi import APIRouter
from pydantic import BaseModel
import os
import json
import time
from local_storage import get_storage

router = APIRouter()

class DashboardMutationRequest(BaseModel):
    dashboard: dict
    instruction: str
    document_id: str = "demo-doc-123"

@router.post("/mutate-dashboard")
async def mutate_dashboard(payload: DashboardMutationRequest):
    dashboard = payload.dashboard
    instruction = payload.instruction
    document_id = payload.document_id
    
    # Fetch Context from DB
    storage = get_storage()
    rows = []
    anomalies = []
    try:
        rows = storage.get_rows(document_id, limit=5)
        anomalies = storage.get_anomalies(document_id)
    except Exception as e:
        print(f"DB Fetch Error: {e}")

    # Format context for AI
    data_context = f"Financial Data Sample: {json.dumps([r.get('raw_json') for r in rows])}\n"
    data_context += f"Detected Anomalies: {json.dumps(anomalies)}\n"

    time.sleep(1.0) 

    try:
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            client = OpenAI()
            
            system_prompt = """You are Parity, a senior financial analyst AI. 
            Your goal is to update the JSON dashboard to answer the user's question using the provided financial data.
            
            Personality:
            - Professional, concise, and data-driven.
            - Use financial terminology (EBITDA, YoY, Margin).
            - If the data supports it, highlight risks.

            Output Format:
            Return a JSON object with two keys:
            1. "dashboard": The updated dashboard schema (cards array).
            2. "message": A short, natural language response to the user explaining what you changed or what you found.
            """

            user_prompt = f"""
            Current Dashboard: {json.dumps(dashboard)}
            
            Context Data:
            {data_context}

            User Instruction: {instruction}

            Update the dashboard to visualize the answer. 
            """

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            return result

    except Exception as e:
        print(f"OpenAI failed: {e}")

    # ... existing mock fallback ...
    new_dashboard = dashboard.copy()
    
    if "revenue" in instruction.lower() or "growth" in instruction.lower():
        new_dashboard["cards"] = [
            {
                "type": "metric",
                "title": "Annual Revenue Run Rate",
                "value": "$4.2M",
                "trend": "+15%",
                "status": "positive"
            },
            {
                "type": "line_chart",
                "title": "Revenue Trend (12 Months)",
                "data": [
                    {"name": "Jan", "value": 300},
                    {"name": "Feb", "value": 310},
                    {"name": "Mar", "value": 340},
                    {"name": "Apr", "value": 330},
                    {"name": "May", "value": 360},
                    {"name": "Jun", "value": 380},
                    {"name": "Jul", "value": 390},
                    {"name": "Aug", "value": 410},
                    {"name": "Sep", "value": 405},
                    {"name": "Oct", "value": 430},
                    {"name": "Nov", "value": 450},
                    {"name": "Dec", "value": 480}
                ]
            },
            {
                "type": "insights",
                "title": "Revenue Analysis",
                "items": [
                    "Consistent MoM growth averaging 4%.",
                    "Q4 shows strongest performance due to seasonality.",
                    "churn rate remains low at 2%."
                ]
            }
        ]
    elif "profit" in instruction.lower() or "margin" in instruction.lower():
         new_dashboard["cards"] = [
            {
                "type": "metric",
                "title": "Net Profit Margin",
                "value": "22%",
                "trend": "+2.5%",
                "status": "positive"
            },
             {
                "type": "metric",
                "title": "Gross Margin",
                "value": "68%",
                "trend": "-1%",
                "status": "warning"
            },
            {
                "type": "line_chart",
                "title": "EBITDA vs Net Income",
                "data": [
                    {"name": "Q1", "value": 120},
                    {"name": "Q2", "value": 140},
                    {"name": "Q3", "value": 110},
                    {"name": "Q4", "value": 180}
                ]
            }
         ]
    else:
        # Default add a card
        new_dashboard["cards"].append({
            "type": "metric",
            "title": "New Metric",
            "value": "100",
            "trend": "0%",
            "status": "neutral"
        })

    return {
        "dashboard": new_dashboard, 
        "message": "I've updated the dashboard based on your keywords (Demo Fallback)."
    }
