from fastapi import APIRouter
from pydantic import BaseModel
import os
import json
import asyncio
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

    await asyncio.sleep(1.0)

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

    return {
        "error_code": "LLM_UNAVAILABLE",
        "error_message": "LLM is unavailable (missing OPENAI_API_KEY or upstream failure).",
        "next_action": "configure_openai_key",
    }
