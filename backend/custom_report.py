from fastapi import APIRouter
from pydantic import BaseModel
import os
import asyncio

router = APIRouter()

class CustomReportRequest(BaseModel):
    data_summary: str

@router.post("/generate-custom-report")
async def generate_custom_report(payload: CustomReportRequest):
    data_summary = payload.data_summary
    
    # Simulate processing delay
    await asyncio.sleep(2)

    try:
        # Try to use OpenAI if key exists
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are Parity, an AI financial analyst."},
                    {"role": "user", "content": f"Generate a structured investment analysis report for this data: {data_summary}"}
                ]
            )
            return {"report": response.choices[0].message.content}
    except Exception as e:
        print(f"OpenAI failed: {e}")

    return {
        "report": "LLM is unavailable. Unable to generate an interpretive report.",
        "error_code": "LLM_UNAVAILABLE",
        "error_message": "LLM is unavailable (missing OPENAI_API_KEY or upstream failure).",
        "next_action": "configure_openai_key",
    }
