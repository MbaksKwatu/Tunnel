from fastapi import APIRouter
from pydantic import BaseModel
import os
import time

router = APIRouter()

class EmailDraftRequest(BaseModel):
    missing_info: str

@router.post("/draft-review-email")
async def draft_review_email(payload: EmailDraftRequest):
    missing_info = payload.missing_info
    
    time.sleep(1.5)

    try:
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            client = OpenAI()
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":"Write professional emails for financial due diligence."},
                    {"role":"user","content":f"Draft a request for missing documents: {missing_info}"}
                ]
            )
            return {"email": res.choices[0].message.content}
    except Exception as e:
        print(f"OpenAI failed: {e}")

    # Mock Response
    email = f"""Subject: Outstanding Items for Due Diligence - FundIQ Review

Dear Team,

I hope this email finds you well.

As we proceed with our financial review, we have identified a few items that require your attention. Could you please provide the following documentation at your earliest convenience:

{missing_info}

Providing these documents will allow us to finalize our assessment and move forward with the next steps of the process.

If you have any questions or if any of these items are not applicable, please let us know.

Best regards,

Parity Investment Team
"""
    return {"email": email}
