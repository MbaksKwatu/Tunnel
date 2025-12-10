
🟦 
PARITY — MVP DEMO IMPLEMENTATION PLAN (WINDSURF MASTER INSTRUCTIONS)


Paste this entire file into a Windsurf tab titled:
PARITY_BUILD_PLAN.md



🚀 
PARITY — AI-FIRST FINANCIAL INTELLIGENCE PLATFORM (MVP DEMO BUILD)


This document contains all instructions required to implement the new AI-native demo workflows for Parity within the existing Tunnel codebase.

Parity replaces all FundIQ branding.
Parity = SME Investment Intelligence + AI-Native Workflow.



✅ 
OBJECTIVE FOR THIS SPRINT


Build a demo-ready version of Parity with:

Upload → Decision Flow
Generate Reports

IC Report (existing)
Custom AI report (new)

Actions

Evaluate with AI Assistant (chat + dashboard generation)
Request Review (email draft generation)

Dynamic Dashboard Rendering
AI glue to link data → insights → visualization


Execution time: 1–2 hours
Priority: demo stability > feature completeness



🧠 
CORE PRINCIPLES


Keep existing parsing + anomaly engine intact.
Build new flows as separate pages to avoid breaking anything.
Use JSON schemas for dynamic dashboard generation.
Use LLM tools to mutate dashboard state.
Remove all “FundIQ” branding → replace with Parity (UI labels + titles only).




📁 
PROJECT STRUCTURE IMPACTED


Front-end additions:
/app/dashboard/page.tsx
/app/reports/page.tsx
/app/actions/page.tsx
/app/actions/evaluate/page.tsx
/app/actions/request-review/page.tsx
/components/DynamicDashboard.tsx
/components/MetricCard.tsx
/components/LineChartCard.tsx
/components/InsightList.tsx
/lib/dashboardSchema.ts
Backend additions:
backend/custom_report.py
backend/routes/custom_report.py
backend/routes/llm_actions.py
backend/routes/dashboard_mutation.py



🟨 
PHASE 1 — Add Action Buttons After Upload


Modify /app/dashboard/page.tsx after file processing completes.

Add:
<div className="mt-8 flex gap-4">
  <Button onClick={() => router.push('/reports')} variant="default">
    Generate Report
  </Button>

  <Button onClick={() => router.push('/actions')} variant="outline">
    Take Action
  </Button>
</div>



🟥 
PHASE 2 — REPORTS PAGE


Create:
/app/reports/page.tsx

Two report types:

Investment Committee Report (existing PDF endpoint)
AI-Custom Report (new)


Add UI:
export default function ReportsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Reports</h1>

      <div className="space-y-6">
        <Card>
          <CardHeader><CardTitle>IC Report</CardTitle></CardHeader>
          <CardContent>
            <Button onClick={generateIC}>Generate IC Report</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>AI Custom Report</CardTitle></CardHeader>
          <CardContent>
            <Button onClick={generateCustomReport}>Generate Custom Report</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}



🟦 
BACKEND — AI CUSTOM REPORT


Create file:
backend/custom_report.py
from fastapi import APIRouter
from openai import OpenAI

router = APIRouter()

@router.post("/generate-custom-report")
async def generate_custom_report(payload: dict):
    data_summary = payload.get("data_summary", "")

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are Parity, an AI financial analyst."},
            {"role": "user", "content": f"Generate a structured investment analysis report for this data: {data_summary}"}
        ]
    )

    return {"report": response.choices[0].message["content"]}
Add router to backend/main.py:
app.include_router(custom_report.router)



🟧 
PHASE 3 — ACTIONS PAGE


Create:

/app/actions/page.tsx
export default function ActionsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Actions</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        <Card>
          <CardHeader><CardTitle>Evaluate with Assistant</CardTitle></CardHeader>
          <CardContent>
            <Button onClick={() => router.push('/actions/evaluate')}>
              Open Assistant
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Request Review</CardTitle></CardHeader>
          <CardContent>
            <Button onClick={() => router.push('/actions/request-review')}>
              Compose Request
            </Button>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}



🟦 
PHASE 4 — AI ASSISTANT (CHAT + DASHBOARD)


Create:

/app/actions/evaluate/page.tsx

Features:

Chat UI
Dashboard rendering area
History persistence via React state
Backend routes to mutate dashboard schema



Backend API to mutate dashboard


File: backend/routes/dashboard_mutation.py
@router.post("/mutate-dashboard")
async def mutate_dashboard(payload: dict):
    dashboard = payload["dashboard"]
    instruction = payload["instruction"]

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You modify a JSON dashboard schema."},
            {"role": "user", "content": f"Dashboard: {dashboard}\nInstruction: {instruction}"}
        ]
    )

    return {"dashboard": response.choices[0].message["content"]}



🟩 
PHASE 5 — Dynamic Dashboard


File:
/components/DynamicDashboard.tsx
export default function DynamicDashboard({ schema }) {
  return (
    <div className="grid gap-4">
      {schema.cards.map((card, i) => {
        if (card.type === "metric") return <MetricCard key={i} data={card} />;
        if (card.type === "line_chart") return <LineChartCard key={i} data={card} />;
        if (card.type === "insights") return <InsightList key={i} data={card} />;
      })}
    </div>
  );
}



🟥 
PHASE 6 — REQUEST REVIEW


Create:

/app/actions/request-review/page.tsx

Flow:

AI generates request email
User edits
Optionally send


Backend route:
@router.post("/draft-review-email")
async def draft_review_email(payload: dict):
    missing_info = payload.get("missing_info","")
    client = OpenAI()
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"Write professional emails for financial due diligence."},
            {"role":"user","content":f"Draft a request for missing documents: {missing_info}"}
        ]
    )
    return {"email": res.choices[0].message["content"]}



🟦 
PHASE 7 — BRANDING UPDATE
Search and replace:
FundIQ → Parity
Tunnel → Parity Tunnel (optional)

Update:

Titles
Logo placeholder
Page headings
Report headers
NO change to filenames unless cosmetic.



🟨 
PHASE 8 — DEMO HARDENING
Disable auth (if needed)
Preload documents
Remove error modals
Add "Demo Mode" badge
Hide non-functional buttons
Add sample questions like:

“Explain Q2 revenue drop”
“Generate 12-month forecast”
“Build profitability dashboard”





🟫 
TESTING CHECKLIST

Upload
✔ PDF/CSV/XLSX parse
✔ Document list updates
✔ Sample anomalies load


Reports
✔ IC Report PDF works
✔ AI Custom Report returns Markdown


Actions
✔ Assistant chat flows
✔ Dashboard mutation renders
✔ Request Review email draft works



Implement tasks in this order:

Batch 1
Add post-upload buttons
Reports page
Actions page



Batch 2
AI Custom Report
Evaluate with Assistant UI + backend
Dynamic Dashboard renderer



Batch 3
Request Review + email
Branding change
Demo hardening
