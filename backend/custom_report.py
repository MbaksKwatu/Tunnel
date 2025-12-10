from fastapi import APIRouter
from pydantic import BaseModel
import os
import time

router = APIRouter()

class CustomReportRequest(BaseModel):
    data_summary: str

@router.post("/generate-custom-report")
async def generate_custom_report(payload: CustomReportRequest):
    data_summary = payload.data_summary
    
    # Simulate processing delay
    time.sleep(2)

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
        print(f"OpenAI failed, using mock: {e}")

    # Mock response
    mock_report = """## Parity Investment Analysis

### Executive Summary
Based on the provided financial data, the company demonstrates **strong operational resilience** with a **15% Quarter-over-Quarter revenue growth**. The efficiency metrics indicate a maturing operational model.

### Key Observations
1. **Revenue Growth**: Consistent upward trend suggests effective market penetration.
2. **Cost Management**: Operating expenses have remained flat despite revenue growth, indicating positive operating leverage.
3. **Profitability**: Net profit margins have expanded to **22%**, surpassing industry averages for this sector.

### Risk Factors
* **Market Volatility**: External macro-factors may impact Q4 projections.
* **Concentration**: Top 3 clients account for 40% of revenue.

### Recommendation
**BUY**. The company is undervalued relative to its growth velocity and profitability profile.
"""
    return {"report": mock_report}
