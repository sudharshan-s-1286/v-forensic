import os
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import anthropic
import pdfplumber
import json
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="V-FORENSIC API")

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------
# MODELS
# -----------------

class CompanyInfo(BaseModel):
    name: str = ""
    loan_amount: float = 0
    loan_purpose: str = ""
    sector: str = ""
    promoter_name: str = ""
    din: str = ""

class ForensicRequest(BaseModel):
    company: CompanyInfo
    gst_text: str = ""
    bank_text: str = ""
    annual_report_text: str = ""
    itr_text: str = ""
    demo_mode: bool = False

class SectorRequest(BaseModel):
    sector: str
    company: str

class NewsRequest(BaseModel):
    company: str
    sector: str
    promoter: str

class LitigationRequest(BaseModel):
    company: str
    director_name: str

class NotesRequest(BaseModel):
    company: str
    notes: str

class ScoreRequest(BaseModel):
    company: CompanyInfo
    forensic_results: Any
    research_results: Any
    litigation_results: Any
    officer_adjustments: Any

class CAMRequest(BaseModel):
    company: CompanyInfo
    forensic_results: Any
    research_results: Any
    litigation_results: Any
    score_results: Any
    officer_notes: str = ""

# -----------------
# HELPER: CLAUDE
# -----------------
def call_claude(api_key: str, system_prompt: str, user_prompt: str, max_tokens: int = 2000):
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6", # Per exact instructions
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        # Extract text block
        text = response.content[0].text
        
        # Strip markdown fences if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"Claude API Error: {str(e)}")
        # Sometimes Claude might just return text for CAM
        try:
            # If not JSON (like CAM endpoint)
            return text.strip()
        except:
            raise HTTPException(status_code=500, detail=str(e))

def call_claude_text(api_key: str, system_prompt: str, user_prompt: str, max_tokens: int = 4000):
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# -----------------
# API ENDPOINTS
# -----------------

@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    api_key = request.headers.get("X-Api-Key")
    
    text = ""
    pages_count = 0
    try:
        # Save temp 
        file_location = f"/tmp/{file.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(file.file.read())

        if file.filename.lower().endswith(".pdf"):
            with pdfplumber.open(file_location) as pdf:
                pages_count = len(pdf.pages)
                for page in pdf.pages:
                    # Extract raw text
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    # Extract tables separately
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            clean_row = [str(cell) if cell is not None else "" for cell in row]
                            text += " | ".join(clean_row) + "\n"
                    text += "\n--PAGE BREAK--\n"

        # Limit to 12000 chars as requested
        text = text[:12000]
        os.remove(file_location)
        
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        text = "[PDF extraction note: error]"

    return {
        "filename": file.filename,
        "text": text,
        "pages": pages_count
    }

@app.post("/api/analyze/forensic")
async def analyze_forensic(req: Request, data: ForensicRequest):
    api_key = req.headers.get("X-Api-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API Key required")
        
    system = "You are V-Forensic, an expert credit forensics engine for Indian NBFC lending. Analyse documents and perform forensic cross-referencing. Be precise and realistic. Respond with ONLY valid JSON, no markdown fences, no extra text."
    
    user = f"""Perform forensic credit analysis.
Company: {data.company.name}
Sector: {data.company.sector}
Loan: Rs.{data.company.loan_amount} Crore ({data.company.loan_purpose})
Promoter: {data.company.promoter_name} | DIN: {data.company.din}
Demo Mode: {str(data.demo_mode).lower()}

Document Data:
GST Returns: {data.gst_text[:3000] if data.gst_text else 'Not provided'}
Bank Statement: {data.bank_text[:3000] if data.bank_text else 'Not provided'}
Annual Report: {data.annual_report_text[:3000] if data.annual_report_text else 'Not provided'}
ITR: {data.itr_text[:2000] if data.itr_text else 'Not provided'}

If demo_mode is true, generate realistic simulated forensic data for a textile company with some flags.
If real documents provided, analyse them carefully.

Return ONLY this exact JSON structure:
{{
  "revenue_phantom": {{
    "gst_revenue": <float crore>,
    "bank_credits": <float crore>,
    "gap_amount": <float crore>,
    "gap_percentage": <float>,
    "flagged": <bool>,
    "severity": "PASS"|"MEDIUM"|"HIGH"|"CRITICAL",
    "explanation": "<2-3 sentence explanation>"
  }},
  "ghost_payroll": {{
    "declared_expense": <float crore>,
    "actual_outflows": <float crore>,
    "discrepancy": <float crore>,
    "flagged": <bool>,
    "severity": "PASS"|"MEDIUM"|"HIGH"|"CRITICAL",
    "explanation": "<2-3 sentence explanation>"
  }},
  "promoter_shadow": {{
    "din": "<string>",
    "total_companies": <int>,
    "struck_off_count": <int>,
    "active_count": <int>,
    "companies": [{{"name": "...", "status": "...", "year": "..."}}],
    "flagged": <bool>,
    "severity": "PASS"|"MEDIUM"|"HIGH"|"CRITICAL",
    "explanation": "<2-3 sentence explanation>"
  }},
  "circular_trading": {{
    "entities_mapped": <int>,
    "loops_detected": <int>,
    "loop_chains": ["<string>"],
    "flagged": <bool>,
    "severity": "PASS"|"MEDIUM"|"HIGH"|"CRITICAL",
    "explanation": "<2-3 sentence explanation>"
  }}
}}"""

    return call_claude(api_key, system, user)

@app.post("/api/research/sector")
async def research_sector(req: Request, data: SectorRequest):
    api_key = req.headers.get("X-Api-Key")
    system = "You are a senior credit research analyst for Indian markets. Respond with ONLY valid JSON."
    user = f"""Sector intelligence for credit assessment.
Sector: {data.sector} | Company: {data.company}
Return JSON:
{{
  "sector": "{data.sector}", 
  "risk_rating": "LOW"|"MEDIUM"|"HIGH",
  "outlook": "POSITIVE"|"STABLE"|"NEGATIVE",
  "trends": ["5 strings"],
  "headwinds": ["3 strings"],
  "tailwinds": ["2 strings"],
  "impact_summary": "string",
  "key_metrics": {{
    "avg_npa_rate": "string",
    "yoy_growth": "string",
    "regulatory_risk": "LOW"|"MEDIUM"|"HIGH"
  }}
}}"""
    return call_claude(api_key, system, user)

@app.post("/api/research/news")
async def research_news(req: Request, data: NewsRequest):
    api_key = req.headers.get("X-Api-Key")
    system = "You are a news analyst for Indian credit risk due diligence. Respond with ONLY valid JSON."
    user = f"""Simulate news intelligence search.
Company: {data.company} | Sector: {data.sector} | Promoter: {data.promoter}
Generate 4-5 company news and 2-3 promoter news items.
Return JSON:
{{
  "company_news": [{{"headline": "...", "source": "...", "date": "...", "summary": "...", "sentiment": "NEGATIVE"|"NEUTRAL"|"POSITIVE"}}],
  "promoter_news": [{{"headline": "...", "source": "...", "date": "...", "summary": "...", "sentiment": "NEGATIVE"|"NEUTRAL"|"POSITIVE"}}],
  "overall_news_risk": "CLEAN"|"MEDIUM"|"HIGH",
  "adverse_signal_count": <int>,
  "summary": "string"
}}"""
    return call_claude(api_key, system, user)

@app.post("/api/research/litigation")
async def research_litigation(req: Request, data: LitigationRequest):
    api_key = req.headers.get("X-Api-Key")
    system = "You are a legal researcher for Indian NBFCs. Respond with ONLY valid JSON."
    user = f"""Simulate litigation scan for Indian courts.
Company: {data.company} | Director: {data.director_name}
Return JSON:
{{
  "cases": [{{"case_no": "...", "court": "...", "type": "...", "year": "...", "severity": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL", "summary": "...", "status": "Pending"|"Disposed"|"Settled"}}],
  "total_cases": <int>,
  "high_severity_count": <int>,
  "critical_count": <int>,
  "overall_litigation_risk": "CLEAN"|"LOW"|"MEDIUM"|"HIGH"|"CRITICAL",
  "summary": "string"
}}"""
    return call_claude(api_key, system, user)

@app.post("/api/notes/process")
async def process_notes(req: Request, data: NotesRequest):
    api_key = req.headers.get("X-Api-Key")
    system = "You are a credit officer assistant. Standardize notes and generate score adjustments between -20 and +10. Respond ONLY in valid JSON."
    user = f"""Process site visit notes and return score adjustments.
Company: {data.company} | Notes: {data.notes}
Return JSON:
{{
  "capacity_adjustment": <int (-20 to +10)>,
  "character_adjustment": <int>,
  "collateral_adjustment": <int>,
  "capital_adjustment": <int>,
  "conditions_adjustment": <int>,
  "risk_signals": ["string array"],
  "positive_signals": ["string array"],
  "summary": "string"
}}"""
    return call_claude(api_key, system, user)

@app.post("/api/score/calculate")
async def calculate_score(req: Request, data: ScoreRequest):
    api_key = req.headers.get("X-Api-Key")
    system = "You are a credit scoring engine for Indian NBFC lending. Calculate Five Cs scores. Respond with ONLY JSON."
    user = f"""Calculate credit scores.
Company: {data.company.name} | Sector: {data.company.sector}
Loan: Rs.{data.company.loan_amount} Crore | Purpose: {data.company.loan_purpose}

Forensic: {json.dumps(data.forensic_results)}
Research: {json.dumps(data.research_results)}
Litigation: {json.dumps(data.litigation_results)}
Officer Adjustments: {json.dumps(data.officer_adjustments)}

Apply heavy penalties for HIGH/CRITICAL flags.
Approved amount = % of requested based on risk.

Return ONLY:
{{
  "character_score": <int 0-100>,
  "capacity_score": <int 0-100>,
  "capital_score": <int 0-100>,
  "collateral_score": <int 0-100>,
  "conditions_score": <int 0-100>,
  "master_score": <int 0-100>,
  "decision": "APPROVE"|"CONDITIONAL_APPROVE"|"REJECT",
  "approved_amount": <float>,
  "interest_rate": <float>,
  "tenor_months": <int>,
  "conditions": ["string array 4 items"],
  "key_risks": ["string array 3 items"],
  "shap_factors": [{{"factor": "string", "impact": <int>, "direction": "positive"|"negative"}}],
  "score_rationale": "string",
  "icr": <float>,
  "dscr": <float>,
  "debt_equity": <float>
}}"""
    return call_claude(api_key, system, user)

@app.post("/api/cam/generate")
async def generate_cam(req: Request, data: CAMRequest):
    api_key = req.headers.get("X-Api-Key")
    system = "You are a senior credit analyst at an Indian NBFC. Write professional Credit Appraisal Memos in formal Indian banking style. Use Rs. symbol, Indian number formatting (Crore/Lakh). Be specific with all numbers."
    user = f"""Write a complete Credit Appraisal Memorandum.

Company: {data.company.name} | Loan: Rs.{data.company.loan_amount} Crore | Purpose: {data.company.loan_purpose}
Sector: {data.company.sector} | Promoter: {data.company.promoter_name} (DIN: {data.company.din})
Date: [today's date] | Ref: CAM-847291

Forensic Analysis:
{json.dumps(data.forensic_results)}

Research & Sector:
{json.dumps(data.research_results)}
{json.dumps(data.litigation_results)}

Credit Score Results:
{json.dumps(data.score_results)}

Officer Notes:
{data.officer_notes}

Write the complete professional CAM in markdown with these exact sections and in this order:

# CREDIT APPRAISAL MEMORANDUM

**Company:** {data.company.name} | **Date:** [insert current date] | **Reference:** CAM-[random 6-digit number]

---

## 1. Company Overview
[Business description, sector, incorporation, years operating, primary products/services]

## 2. Loan Request Details
[Amount, purpose, proposed tenor, how funds will be used]

## 3. Promoter Background
[Director name, DIN, company history table, character assessment]

## 4. Financial Analysis
[Revenue trend, profitability, working capital position.
Include a markdown table for key ratios:
| Ratio | Value | Benchmark | Assessment |
|-------|-------|-----------|------------|
with DSCR, ICR, Debt/Equity, Revenue Growth]

## 5. Forensic Findings
[Detailed finding for each of 4 checks. State exact numbers. Clearly flag any HIGH or CRITICAL findings.]

## 6. External Intelligence
[Sector outlook summary, news findings, litigation summary]

## 7. Field Observations
[Summary of officer site visit notes if provided]

## 8. Five Cs Scorecard
[Markdown table with all 5 scores and master score]

## 9. Key Risk Factors
[Numbered list of all identified risks, most critical first]

## 10. Recommendation & Conditions
[Decision box, approved amount, rate, tenor. Numbered list of all conditions. Recommended monitoring requirements.]

## 11. Disclaimer
This Credit Appraisal Memorandum was prepared by V-Forensic AI Credit Intelligence System. All findings are based on documents submitted and AI-assisted analysis. This report is subject to final review and approval by the Credit Committee. Lending decisions must comply with all applicable RBI guidelines and internal credit policies.

---
*V-Forensic | Corporate Credit Intelligence | Confidential*"""

    cam_markdown = call_claude_text(api_key, system, user, max_tokens=4000)
    return {"cam_text": cam_markdown}


# -----------------
# MOUNT STATIC FRONTEND
# -----------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True))
