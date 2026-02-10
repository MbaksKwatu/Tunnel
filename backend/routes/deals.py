"""
Deal Management API Routes
Handles deals, thesis, evidence, and judgment endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import uuid
import logging
from datetime import datetime

from auth import get_current_user
import json
from local_storage import get_storage  # Returns SupabaseStorage only
from judgment_engine import JudgmentEngine
from parsers import get_parser, PasswordRequiredError
from anomaly_engine import AnomalyDetector
from insight_generator import InsightGenerator

logger = logging.getLogger(__name__)
router = APIRouter()

# ================ DEBUG LOG HELPER (temporary) =================
DEBUG_LOG_PATH = "/Users/mbakswatu/Desktop/Fintelligence/.cursor/debug.log"

def debug_log(location: str, message: str, data: Dict[str, Any], run_id: str):
    try:
        with open(DEBUG_LOG_PATH, "a") as _f:
            _f.write(json.dumps({
                "id": f"log_{datetime.utcnow().timestamp()}",
                "timestamp": datetime.utcnow().isoformat(),
                "location": location,
                "message": message,
                "data": data,
                "runId": run_id
            }) + "\n")
    except Exception:
        pass

# Initialize judgment engine
judgment_engine = JudgmentEngine()

# Initialize document processing components
anomaly_detector = AnomalyDetector()
insight_generator = InsightGenerator()

# ==================== PYDANTIC MODELS ====================

class DealCreate(BaseModel):
    company_name: str
    sector: str
    geography: str
    deal_type: str
    stage: str
    revenue_usd: Optional[float] = None

class DealUpdate(BaseModel):
    company_name: Optional[str] = None
    sector: Optional[str] = None
    geography: Optional[str] = None
    deal_type: Optional[str] = None
    stage: Optional[str] = None
    revenue_usd: Optional[float] = None
    status: Optional[str] = None

class ThesisCreate(BaseModel):
    investment_focus: Optional[str] = None
    sector_preferences: Optional[List[str]] = None
    geography_constraints: Optional[List[str]] = None
    stage_preferences: Optional[List[str]] = None
    min_revenue_usd: Optional[float] = None
    kill_conditions: Optional[List[str]] = None
    governance_requirements: Optional[List[str]] = None
    financial_thresholds: Optional[Dict[str, Any]] = None
    data_confidence_tolerance: Optional[str] = None
    impact_requirements: Optional[List[str]] = None
    weights: Optional[Dict[str, float]] = None
    name: Optional[str] = None
    is_default: Optional[bool] = False

class ThesisUpdate(BaseModel):
    investment_focus: Optional[str] = None
    sector_preferences: Optional[List[str]] = None
    geography_constraints: Optional[List[str]] = None
    stage_preferences: Optional[List[str]] = None
    min_revenue_usd: Optional[float] = None
    kill_conditions: Optional[List[str]] = None
    governance_requirements: Optional[List[str]] = None
    financial_thresholds: Optional[Dict[str, Any]] = None
    data_confidence_tolerance: Optional[str] = None
    impact_requirements: Optional[List[str]] = None
    weights: Optional[Dict[str, float]] = None
    name: Optional[str] = None
    is_default: Optional[bool] = None

class AskRequest(BaseModel):
    message: str

# ==================== HELPER FUNCTIONS ====================

class DictWrapper:
    """Wrapper to allow attribute access on dictionaries for judgment engine"""
    def __init__(self, data: Dict[str, Any]):
        self._data = data
    
    def __getattr__(self, name):
        return self._data.get(name)

def dict_to_deal(deal_dict: Dict[str, Any]) -> Any:
    """Convert storage dict to Deal-like object for judgment engine"""
    # Create a wrapper that allows attribute access
    class DealWrapper:
        def __init__(self, data):
            self.id = data.get('id')
            self.company_name = data.get('company_name')
            self.sector = data.get('sector')
            self.geography = data.get('geography')
            self.deal_type = data.get('deal_type')
            self.stage = data.get('stage')
            self.revenue_usd = data.get('revenue_usd')
            self.created_by = data.get('created_by')
            self.status = data.get('status', 'draft')
            self.created_at = data.get('created_at')
    
    return DealWrapper(deal_dict)

def dict_to_evidence(evidence_dict: Dict[str, Any]) -> DictWrapper:
    """Convert storage dict to Evidence-like object for judgment engine"""
    class EvidenceWrapper:
        def __init__(self, data):
            self.id = data.get('id')
            self.deal_id = data.get('deal_id')
            self.document_id = data.get('document_id')
            self.evidence_type = data.get('evidence_type')
            self.evidence_subtype = data.get('evidence_subtype')
            self.extracted_data = data.get('extracted_data')
            self.confidence_score = data.get('confidence_score', 0.7)
            self.uploaded_at = data.get('uploaded_at')
    
    return EvidenceWrapper(evidence_dict)

def dict_to_thesis(thesis_dict: Dict[str, Any]) -> Any:
    """Convert storage dict to Thesis-like object for judgment engine"""
    class ThesisWrapper:
        def __init__(self, data):
            self.id = data.get('id')
            self.fund_id = data.get('fund_id')
            self.investment_focus = data.get('investment_focus')
            self.sector_preferences = data.get('sector_preferences')
            self.geography_constraints = data.get('geography_constraints')
            self.stage_preferences = data.get('stage_preferences')
            self.min_revenue_usd = data.get('min_revenue_usd')
            self.kill_conditions = data.get('kill_conditions')
            self.governance_requirements = data.get('governance_requirements')
            self.financial_thresholds = data.get('financial_thresholds')
            self.data_confidence_tolerance = data.get('data_confidence_tolerance')
            self.impact_requirements = data.get('impact_requirements')
            self.weights = data.get('weights')
            self.name = data.get('name')
            self.is_default = data.get('is_default', False)
    
    return ThesisWrapper(thesis_dict)

def verify_deal_ownership(deal: Dict[str, Any], user_id: str):
    """Verify that a deal belongs to the current user"""
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    if deal.get('created_by') != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to access this deal")

# ==================== THESIS ENDPOINTS ====================

@router.post("/thesis")
async def create_thesis(
    thesis_data: ThesisCreate,
    current_user: Any = Depends(get_current_user)
):
    """Create or update user's investment thesis"""
    try:
        storage = get_storage()  # Always returns SupabaseStorage (raises if not configured)
        user_id = current_user.id
        debug_log("deals.py:create_thesis", "start", {"user_id": user_id}, "api-health")
        
        # Check if user already has a thesis
        result = storage.supabase.table('thesis').select('*').eq('fund_id', user_id).execute()
        existing_thesis = result.data[0] if result.data else None
        
        # Convert to dict and only include fields that exist in the database
        thesis_dict = thesis_data.dict(exclude_none=True)
        thesis_dict['fund_id'] = user_id
        
        # Remove fields that might not exist in database schema
        # Keep only fields that are safe to insert/update
        safe_fields = {
            'fund_id': thesis_dict['fund_id'],
            'investment_focus': thesis_dict.get('investment_focus'),
            'sector_preferences': thesis_dict.get('sector_preferences'),
            'geography_constraints': thesis_dict.get('geography_constraints'),
            'stage_preferences': thesis_dict.get('stage_preferences'),
            'min_revenue_usd': thesis_dict.get('min_revenue_usd'),
            'kill_conditions': thesis_dict.get('kill_conditions'),
            'governance_requirements': thesis_dict.get('governance_requirements'),
            'financial_thresholds': thesis_dict.get('financial_thresholds'),
            'data_confidence_tolerance': thesis_dict.get('data_confidence_tolerance'),
            'impact_requirements': thesis_dict.get('impact_requirements'),
            'weights': thesis_dict.get('weights'),
            'name': thesis_dict.get('name'),
            'is_default': thesis_dict.get('is_default', False)
        }
        
        # Remove None values
        safe_fields = {k: v for k, v in safe_fields.items() if v is not None}
        
        if existing_thesis:
            # Update existing thesis - only update fields that exist
            result = storage.supabase.table('thesis').update(safe_fields).eq('id', existing_thesis['id']).execute()
            thesis = result.data[0] if result.data else existing_thesis
        else:
            # Create new thesis
            safe_fields['id'] = str(uuid.uuid4())
            safe_fields['is_default'] = safe_fields.get('is_default', True)
            result = storage.supabase.table('thesis').insert(safe_fields).execute()
            thesis = result.data[0] if result.data else None
        
        if not thesis:
            raise HTTPException(status_code=500, detail="Failed to save thesis")
        
        debug_log("deals.py:create_thesis", "success", {"user_id": user_id, "thesis_id": thesis.get("id") if thesis else None}, "api-health")
        return {"thesis": thesis}
    except HTTPException:
        debug_log("deals.py:create_thesis", "error_http", {"detail": "http_exception"}, "api-health")
        raise
    except Exception as e:
        logger.error(f"Error creating thesis: {e}", exc_info=True)
        debug_log("deals.py:create_thesis", "error", {"error": str(e)}, "api-health")
        # Check if it's a column error
        error_str = str(e)
        if 'column' in error_str.lower() and 'not found' in error_str.lower():
            raise HTTPException(
                status_code=500, 
                detail=f"Database schema error: Missing column. Please run the migration: migrations/fix_thesis_table.sql. Error: {error_str}"
            )
        raise HTTPException(status_code=500, detail=f"Failed to create thesis: {str(e)}")

@router.get("/thesis")
async def get_thesis(current_user: Any = Depends(get_current_user)):
    """Get current user's thesis"""
    try:
        storage = get_storage()  # Always returns SupabaseStorage (raises if not configured)
        user_id = str(current_user.id) if current_user.id else None
        if not user_id:
            logger.warning("get_thesis: current_user.id is empty")
            return {"thesis": None}

        logger.info(f"get_thesis: fetching for fund_id={user_id}")
        debug_log("deals.py:get_thesis", "start", {"user_id": user_id}, "api-health")
        # Match fund_id (UUID in DB) - ensure string for PostgREST
        result = storage.supabase.table('thesis').select('*').eq('fund_id', user_id).limit(1).execute()
        thesis = result.data[0] if result.data else None
        if not thesis:
            # Fallback: try ordering by created_at if column exists
            try:
                result = storage.supabase.table('thesis').select('*').eq('fund_id', user_id).order('created_at', desc=True).limit(1).execute()
                thesis = result.data[0] if result.data else None
            except Exception:
                pass
        logger.info(f"get_thesis: found={thesis is not None}")
        debug_log("deals.py:get_thesis", "success", {"user_id": user_id, "has_thesis": thesis is not None}, "api-health")
        return {"thesis": thesis}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting thesis: {e}", exc_info=True)
        debug_log("deals.py:get_thesis", "error", {"error": str(e)}, "api-health")
        raise HTTPException(status_code=500, detail=f"Failed to get thesis: {str(e)}")

@router.put("/thesis")
async def update_thesis(
    thesis_data: ThesisUpdate,
    current_user: Any = Depends(get_current_user)
):
    """Update existing thesis"""
    try:
        storage = get_storage()  # Always returns SupabaseStorage (raises if not configured)
        user_id = current_user.id
        
        # Get existing thesis
        result = storage.supabase.table('thesis').select('*').eq('fund_id', user_id).order('created_at', desc=True).limit(1).execute()
        existing_thesis = result.data[0] if result.data else None
        
        if not existing_thesis:
            raise HTTPException(status_code=404, detail="Thesis not found")
        
        # Update thesis
        update_dict = thesis_data.dict(exclude_none=True)
        result = storage.supabase.table('thesis').update(update_dict).eq('id', existing_thesis['id']).execute()
        thesis = result.data[0] if result.data else existing_thesis
        
        return {"thesis": thesis}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating thesis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update thesis: {str(e)}")

# ==================== DEALS ENDPOINTS ====================

@router.post("/deals")
async def create_deal(
    company_name: str = Form(...),
    sector: str = Form(...),
    geography: str = Form(...),
    deal_type: str = Form(...),
    stage: str = Form(...),
    revenue_usd: Optional[str] = Form(None),
    current_user: Any = Depends(get_current_user)
):
    """Create a new deal"""
    try:
        storage = get_storage()
        user_id = current_user.id
        
        logger.info(f"Creating deal for user_id: {user_id}")
        logger.info(f"Deal data: company_name={company_name}, sector={sector}, geography={geography}")
        
        deal_dict = {
            'company_name': company_name,
            'sector': sector,
            'geography': geography,
            'deal_type': deal_type,
            'stage': stage,
            'revenue_usd': float(revenue_usd) if revenue_usd else None,
            'id': str(uuid.uuid4()),
            'created_by': str(user_id),  # Ensure it's a string
            'status': 'draft',
            'created_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Attempting to insert deal with created_by: {deal_dict['created_by']}")
        
        deal = storage.create_deal(deal_dict)
        
        if not deal:
            logger.error("create_deal returned None - deal was not created")
            raise HTTPException(status_code=500, detail="Failed to create deal - storage returned None")
        
        logger.info(f"Deal created successfully: {deal.get('id')}")
        
        return {"deal": deal}
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid input: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating deal: {e}", exc_info=True)
        logger.error(f"User ID: {current_user.id if hasattr(current_user, 'id') else 'unknown'}")
        raise HTTPException(status_code=500, detail=f"Failed to create deal: {str(e)}")

@router.get("/deals")
async def list_deals(current_user: Any = Depends(get_current_user)):
    """List all deals for current user"""
    try:
        storage = get_storage()
        user_id = current_user.id
        
        logger.info(f"Fetching deals for user_id: {user_id}")
        
        deals = storage.get_deals_by_user(user_id)
        
        logger.info(f"Found {len(deals)} deals for user {user_id}")
        
        # Sort by created_at descending
        if deals:
            deals.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Always return 200 with deals array (even if empty)
        return {"deals": deals or []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing deals: {e}", exc_info=True)
        logger.error(f"User ID: {current_user.id if hasattr(current_user, 'id') else 'unknown'}")
        raise HTTPException(status_code=500, detail=f"Failed to list deals: {str(e)}")

@router.get("/deals/{deal_id}")
async def get_deal(
    deal_id: str,
    current_user: Any = Depends(get_current_user)
):
    """Get single deal details"""
    try:
        storage = get_storage()
        user_id = current_user.id
        
        deal = storage.get_deal(deal_id)
        verify_deal_ownership(deal, user_id)
        
        return {"deal": deal}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get deal: {str(e)}")

@router.delete("/deals/{deal_id}")
async def delete_deal(
    deal_id: str,
    current_user: Any = Depends(get_current_user)
):
    """Delete a deal and all associated data"""
    try:
        storage = get_storage()
        user_id = current_user.id
        
        # Verify ownership before deleting
        deal = storage.get_deal(deal_id)
        verify_deal_ownership(deal, user_id)
        
        success = storage.delete_deal(deal_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete deal")
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting deal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete deal: {str(e)}")

# ==================== EVIDENCE ENDPOINTS ====================

@router.post("/deals/{deal_id}/evidence")
async def upload_evidence(
    deal_id: str,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    current_user: Any = Depends(get_current_user)
):
    """
    Upload evidence document for a deal
    
    This endpoint:
    1. Processes the document (parses, extracts data)
    2. Runs anomaly detection
    3. Generates insights
    4. Creates document record
    5. Links document to deal via evidence record
    """
    try:
        storage = get_storage()
        user_id = current_user.id
        
        # Verify deal exists and belongs to user
        deal = storage.get_deal(deal_id)
        verify_deal_ownership(deal, user_id)
        
        # Read file content
        file_content = await file.read()
        file_type = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        
        # Validate file type
        if file_type not in ['pdf', 'csv', 'xlsx', 'xls']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_type}. Supported: PDF, CSV, XLSX"
            )
        
        # Determine evidence type from filename or file type
        evidence_type = 'document'
        if 'financial' in file.filename.lower() or 'statement' in file.filename.lower():
            evidence_type = 'financial_statements'
        elif 'bank' in file.filename.lower():
            evidence_type = 'bank_statements'
        elif file_type in ['pdf', 'csv', 'xlsx', 'xls']:
            evidence_type = 'financial_data'
        
        # Create document record
        document_id = str(uuid.uuid4())
        document_data = {
            'id': document_id,
            'user_id': user_id,
            'file_name': file.filename,
            'file_type': file_type,
            'file_url': None,  # Direct upload, no URL
            'status': 'processing',
            'upload_date': datetime.utcnow().isoformat()
        }
        storage.store_document(document_data)
        
        try:
            # Parse the file
            parser = get_parser(file_type)
            rows = await parser.parse(file_url=None, file_content=file_content, password=password)
            
            if not rows:
                storage.update_document_status(
                    document_id,
                    'completed',
                    rows_count=0,
                    error_message='No data found in document'
                )
                # Still create evidence record, but with no data
                evidence_data = {
                    'id': str(uuid.uuid4()),
                    'deal_id': deal_id,
                    'document_id': document_id,  # ✅ LINKED!
                    'evidence_type': evidence_type,
                    'extracted_data': {
                        'filename': file.filename,
                        'file_type': file_type,
                        'rows_count': 0,
                        'anomalies_count': 0
                    },
                    'confidence_score': 0.0,
                    'uploaded_at': datetime.utcnow().isoformat()
                }
                evidence = storage.add_evidence(deal_id, evidence_data)
                return {
                    "evidence": evidence,
                    "document_id": document_id,
                    "message": "Document uploaded but no data extracted"
                }
            
            # Store extracted rows
            rows_inserted = storage.store_rows(document_id, rows)
            
            # Run anomaly detection
            anomalies = anomaly_detector.detect_all(rows)
            anomalies_count = 0
            if anomalies:
                anomalies_count = storage.store_anomalies(document_id, anomalies)
            
            # Generate insights
            insights = insight_generator.generate_insights(anomalies)
            
            # Update document status
            storage.update_document_status(
                document_id,
                'completed',
                rows_count=rows_inserted,
                anomalies_count=anomalies_count,
                insights_summary=insights
            )
            
            # Create evidence record WITH document_id linked
            evidence_data = {
                'id': str(uuid.uuid4()),
                'deal_id': deal_id,
                'document_id': document_id,  # ✅ LINKED!
                'evidence_type': evidence_type,
                'extracted_data': {
                    'filename': file.filename,
                    'file_type': file_type,
                    'rows_count': rows_inserted,
                    'anomalies_count': anomalies_count,
                    'has_insights': bool(insights)
                },
                'confidence_score': 0.9 if rows_inserted > 0 else 0.5,
                'uploaded_at': datetime.utcnow().isoformat()
            }
            
            evidence = storage.add_evidence(deal_id, evidence_data)
            
            if not evidence:
                raise HTTPException(status_code=500, detail="Failed to create evidence record")
            
            logger.info(f"✅ Evidence uploaded for deal {deal_id}: document {document_id}, {rows_inserted} rows, {anomalies_count} anomalies")
            
            return {
                "evidence": evidence,
                "document_id": document_id,
                "rows_extracted": rows_inserted,
                "anomalies_count": anomalies_count,
                "message": "Document processed and linked to deal"
            }
            
        except PasswordRequiredError:
            # Update document status
            storage.update_document_status(
                document_id,
                'failed',
                error_message='Password required'
            )
            raise HTTPException(
                status_code=400,
                detail="PASSWORD_REQUIRED"
            )
        except Exception as parse_error:
            # Update document status
            storage.update_document_status(
                document_id,
                'failed',
                error_message=str(parse_error)
            )
            logger.error(f"Error processing evidence document: {parse_error}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process document: {str(parse_error)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading evidence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload evidence: {str(e)}")

@router.get("/deals/{deal_id}/evidence")
async def get_evidence(
    deal_id: str,
    current_user: Any = Depends(get_current_user)
):
    """Get all evidence for a deal"""
    try:
        storage = get_storage()
        user_id = current_user.id
        
        # Verify deal belongs to user
        deal = storage.get_deal(deal_id)
        verify_deal_ownership(deal, user_id)
        
        evidence = storage.get_evidence(deal_id)
        
        return {"evidence": evidence}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting evidence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get evidence: {str(e)}")

# ==================== JUDGMENT ENDPOINTS ====================

@router.post("/deals/{deal_id}/judge")
async def run_judgment(
    deal_id: str,
    current_user: Any = Depends(get_current_user)
):
    """Run judgment engine on a deal"""
    try:
        storage = get_storage()
        user_id = current_user.id
        
        # Verify deal belongs to user
        deal_dict = storage.get_deal(deal_id)
        verify_deal_ownership(deal_dict, user_id)
        
        # Get evidence
        evidence_list = storage.get_evidence(deal_id)
        
        # Get user's thesis (storage is always SupabaseStorage)
        thesis_result = storage.supabase.table('thesis').select('*').eq('fund_id', user_id).order('created_at', desc=True).limit(1).execute()
        thesis_dict = thesis_result.data[0] if thesis_result.data else None
        
        if not thesis_dict:
            raise HTTPException(status_code=400, detail="No thesis found. Please create a thesis first.")
        
        # Convert dicts to model-like objects for judgment engine
        deal_obj = dict_to_deal(deal_dict)
        evidence_objs = [dict_to_evidence(ev) for ev in evidence_list]
        thesis_obj = dict_to_thesis(thesis_dict)
        
        # Run judgment engine
        judgment_result = judgment_engine.judge_deal(deal_obj, evidence_objs, thesis_obj)
        
        # Save judgment to database
        # Convert readiness and alignment scores to string categories expected by frontend
        readiness_score = judgment_result.get('investment_readiness', 0)
        alignment_score = judgment_result.get('thesis_alignment', 0)
        
        # Frontend expects: READY, CONDITIONALLY_READY, NOT_READY
        if readiness_score >= 70:
            readiness_category = "READY"
        elif readiness_score >= 50:
            readiness_category = "CONDITIONALLY_READY"
        else:
            readiness_category = "NOT_READY"
        
        # Frontend expects: ALIGNED, PARTIALLY_ALIGNED, MISALIGNED
        if alignment_score >= 70:
            alignment_category = "ALIGNED"
        elif alignment_score >= 50:
            alignment_category = "PARTIALLY_ALIGNED"
        else:
            alignment_category = "MISALIGNED"
        
        # Confidence level should be uppercase: HIGH, MEDIUM, LOW
        confidence_level = judgment_result.get('confidence_level', 'low').upper()
        
        # Format explanations as dict expected by frontend
        explanations_list = judgment_result.get('explanations', [])
        kill_signals_dict = judgment_result.get('kill_signals', {})
        
        explanations_dict = {
            'investment_readiness': f"Score: {readiness_score:.1f}/100. " + 
                ("Ready for investment consideration." if readiness_category == "READY" else
                 "Conditional readiness - requires additional due diligence." if readiness_category == "CONDITIONALLY_READY" else
                 "Not ready for investment at this time."),
            'thesis_alignment': f"Score: {alignment_score:.1f}/100. " +
                ("Strong alignment with investment thesis." if alignment_category == "ALIGNED" else
                 "Partial alignment - some criteria met." if alignment_category == "PARTIALLY_ALIGNED" else
                 "Limited alignment with investment thesis."),
            'kill_signals': kill_signals_dict.get('detail', 'No kill signals detected.') if kill_signals_dict.get('type') != 'NONE' else 'No kill signals detected.',
            'confidence_level': f"{confidence_level} confidence based on data quality and completeness."
        }
        
        # Add any additional explanation notes from the list
        if isinstance(explanations_list, list) and explanations_list:
            additional_notes = ' '.join(explanations_list)
            explanations_dict['investment_readiness'] += f" {additional_notes}"
        
        judgment_data = {
            'investment_readiness': readiness_category,
            'thesis_alignment': alignment_category,
            'kill_signals': kill_signals_dict,  # Dict with type, reason, detail
            'confidence_level': confidence_level,
            'dimension_scores': judgment_result.get('dimension_scores', {}),
            'explanations': explanations_dict,
            'created_at': datetime.utcnow().isoformat()
        }
        
        judgment = storage.save_judgment(deal_id, judgment_data)
        
        # Update deal status
        storage.update_deal(deal_id, {'status': 'judged'})
        
        return {"judgment": judgment}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running judgment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to run judgment: {str(e)}")

@router.get("/deals/{deal_id}/judgment")
async def get_judgment(
    deal_id: str,
    current_user: Any = Depends(get_current_user)
):
    """Get judgment results for a deal"""
    try:
        storage = get_storage()
        user_id = current_user.id
        
        # Verify deal belongs to user
        deal = storage.get_deal(deal_id)
        verify_deal_ownership(deal, user_id)
        
        judgment = storage.get_judgment(deal_id)
        
        return {"judgment": judgment}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting judgment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get judgment: {str(e)}")

# ==================== ASK PARITY ENDPOINTS ====================

@router.get("/deals/{deal_id}/conversation")
async def get_conversation(
    deal_id: str,
    current_user: Any = Depends(get_current_user)
):
    """Get conversation history for Ask Parity (last 8–10 messages, oldest first)."""
    try:
        storage = get_storage()
        deal = storage.get_deal(deal_id)
        verify_deal_ownership(deal, current_user.id)
        messages = storage.get_conversation_messages(deal_id, limit=10)
        # Return format for frontend: list of {role, content, created_at}
        out = [{"role": m.get("role"), "content": m.get("content", ""), "created_at": m.get("created_at")} for m in messages]
        return {"messages": out}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get conversation: {str(e)}")

@router.post("/deals/{deal_id}/ask")
async def ask_parity(
    deal_id: str,
    body: AskRequest,
    current_user: Any = Depends(get_current_user)
):
    """Ask Parity: deal-scoped AI chat. Option A only: [system_prompt_with_history, current_user_message]."""
    storage = get_storage()
    user_id = current_user.id
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    deal = storage.get_deal(deal_id)
    verify_deal_ownership(deal, user_id)

    # 1. Deal context
    company_name = deal.get("company_name") or "Unknown"
    sector = deal.get("sector") or "Unknown"
    geography = deal.get("geography") or "Unknown"
    stage = deal.get("stage") or "Unknown"

    # 2. Evidence summary from evidence_type
    evidence_list = storage.get_evidence(deal_id)
    financials = any(
        (e.get("evidence_type") or "").lower() in ("financial_statements", "financial_data")
        for e in evidence_list
    )
    bank_statements = any((e.get("evidence_type") or "").lower() == "bank_statements" for e in evidence_list)
    governance = any("governance" in (e.get("evidence_type") or "").lower() for e in evidence_list)

    evidence_fin = "yes" if financials else "no"
    evidence_bank = "yes" if bank_statements else "no"
    evidence_gov = "yes" if governance else "no"

    # 3. Judgment summary (or "Not yet run")
    judgment = storage.get_judgment(deal_id)
    if judgment:
        investment_readiness = judgment.get("investment_readiness") or "Not set"
        thesis_alignment = judgment.get("thesis_alignment") or "Not set"
        confidence_level = judgment.get("confidence_level") or "Not set"
        dims = judgment.get("dimension_scores") or {}
        fin_score = dims.get("financial")
        gov_score = dims.get("governance")
        market_score = dims.get("market")
        team_score = dims.get("team")
        product_score = dims.get("product")
        data_conf_score = dims.get("data_confidence")
        
        financial_score = str(fin_score) if fin_score is not None else "—"
        governance_score = str(gov_score) if gov_score is not None else "—"
        market_score_str = str(market_score) if market_score is not None else "—"
        team_score_str = str(team_score) if team_score is not None else "—"
        product_score_str = str(product_score) if product_score is not None else "—"
        data_conf_score_str = str(data_conf_score) if data_conf_score is not None else "—"
        
        kill = judgment.get("kill_signals") or {}
        if isinstance(kill, dict):
            ktype = kill.get("type") or "NONE"
            kdetail = kill.get("detail") or kill.get("reason") or ""
            kill_summary = f"{ktype}: {kdetail}" if ktype != "NONE" and kdetail else (kdetail or "None")
        else:
            kill_summary = str(kill)
        
        explanations = judgment.get("explanations") or {}
        readiness_explanation = explanations.get("investment_readiness") or ""
        alignment_explanation = explanations.get("thesis_alignment") or ""
        kill_explanation = explanations.get("kill_signals") or ""
        
        missing_evidence = judgment.get("suggested_missing") or []
        missing_list = "\n".join([f"- {m.get('type', 'Unknown')}: {m.get('action', '')}" for m in missing_evidence]) if missing_evidence else "None"
    else:
        investment_readiness = "Not yet run"
        thesis_alignment = "Not yet run"
        confidence_level = "Not yet run"
        financial_score = "—"
        governance_score = "—"
        market_score_str = "—"
        team_score_str = "—"
        product_score_str = "—"
        data_conf_score_str = "—"
        kill_summary = "—"
        readiness_explanation = ""
        alignment_explanation = ""
        kill_explanation = ""
        missing_list = "—"

    # 4. Thesis (or "Not set") — guard against missing created_at column
    try:
        thesis_rows = storage.supabase.table("thesis").select("*").eq("fund_id", user_id).order("created_at", desc=True).limit(1).execute()
    except Exception as e:
        logger.warning(f"Thesis query without created_at ordering (fallback). Error: {e}")
        thesis_rows = storage.supabase.table("thesis").select("*").eq("fund_id", user_id).limit(1).execute()
    thesis = thesis_rows.data[0] if thesis_rows.data else None
    investment_focus = (thesis.get("investment_focus") or "Not set") if thesis else "Not set"
    min_revenue = thesis.get("min_revenue_usd") if thesis else None
    thresholds_str = f"min_revenue_usd: {min_revenue}" if min_revenue is not None else "None"

    # 5. Conversation history (last 8–10, block format inside system prompt)
    history = storage.get_conversation_messages(deal_id, limit=10)
    history_blocks = []
    for m in history:
        role = m.get("role") or "user"
        content = (m.get("content") or "").strip()
        if role == "user":
            history_blocks.append(f"USER:\n{content}")
        else:
            history_blocks.append(f"ASSISTANT (Parity):\n{content}")

    history_section = "\n\n".join(history_blocks) if history_blocks else "(No prior messages.)"

    system_body = f"""You are Parity, an AI investment analyst.

STANCE:
- Think like a calm, experienced investment analyst.
- Be neutral, structured, and precise.
- Prefer clarity over verbosity.
- Avoid speculative language.
- When uncertain, explicitly state what is unknown.

You assist an investment team evaluating a single deal.

DEAL CONTEXT:
- Company: {company_name}
- Sector: {sector}
- Geography: {geography}
- Stage: {stage}

EVIDENCE AVAILABLE:
- Financials: {evidence_fin}
- Bank statements: {evidence_bank}
- Governance docs: {evidence_gov}
(list document types only; do not invent content)

JUDGMENT SUMMARY:
- Investment Readiness: {investment_readiness}
- Thesis Alignment: {thesis_alignment}
- Confidence Level: {confidence_level}
- Dimension Scores:
  * Financial: {financial_score}/100
  * Governance: {governance_score}/100
  * Market: {market_score_str}/100
  * Team: {team_score_str}/100
  * Product: {product_score_str}/100
  * Data Confidence: {data_conf_score_str}/100
- Kill Signals: {kill_summary}
{f"- Readiness Explanation: {readiness_explanation}" if readiness_explanation else ""}
{f"- Alignment Explanation: {alignment_explanation}" if alignment_explanation else ""}
{f"- Kill Signals Explanation: {kill_explanation}" if kill_explanation else ""}
- Missing Evidence Suggestions:
{missing_list}

INVESTMENT THESIS:
- Focus: {investment_focus}
- Minimum thresholds (if any): {thresholds_str}

CONVERSATION HISTORY (STRICT — block format only; last 8–10 messages; never exceed 10):
- Do NOT use inline `User: ... / Parity: ...`.
- Do NOT summarise history.
- Do NOT skip assistant turns.
Below is the prior conversation in block format (USER: then ASSISTANT (Parity):):

{history_section}

RULES:
- Answer concisely (3–6 sentences max, unless user asks for detailed analysis).
- Reference the deal, evidence, or judgment results explicitly when relevant.
- If judgment has been run, you can explain what the scores mean, what the explanations indicate, and what missing evidence might help.
- If data is missing, say what is missing; do not invent.
- Do NOT make investment decisions or recommendations.
- Do NOT invent data.
- Do NOT speak generally about finance unless directly relevant to this deal.
- **Judgment-not-run (CRITICAL):** If judgment has not been run, Parity MUST say: "Judgment has not yet been run for this deal, so I cannot explain scores." Then focus only on evidence availability and open questions; do NOT speculate about scores or readiness. No exceptions.
- **Judgment-available (ENHANCED):** When judgment IS available, Parity can:
  * Explain what the dimension scores indicate (e.g., "Financial score of 65/100 suggests moderate financial strength with room for improvement")
  * Reference the explanations provided (readiness, alignment, kill signals)
  * Discuss what missing evidence might improve the scores
  * Help the user understand the judgment results in context
- **Deal summary (STRICT):** When asked to summarise the deal, Parity may include: company, sector, stage, evidence present (yes/no), judgment status (run / not run), and if run: readiness level, alignment, key scores. Parity must NOT: give opinions, imply readiness beyond what judgment states, suggest decisions, add conclusions.
- **Follow-up suggestions (allowed but constrained):** Parity may suggest 1–2 follow-up checks only, using soft analytical language. Allowed: "It may be useful to clarify…", "The analyst may want to check…", "A remaining open question is…", "The judgment suggests that [missing evidence type] could improve the [dimension] score". Disallowed: "You should…", "Proceed with…", "Approve / reject", "I recommend…"."""

    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="Ask Parity is unavailable (OPENAI_API_KEY not set).")

    try:
        from openai import OpenAI
        client = OpenAI()
        messages = [
            {"role": "system", "content": system_body},
            {"role": "user", "content": message},
        ]
        res = client.chat.completions.create(model="gpt-4o", messages=messages)
        assistant_content = (res.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"Ask Parity OpenAI error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Ask Parity is temporarily unavailable.")

    storage.save_conversation_message(deal_id, "user", message)
    storage.save_conversation_message(deal_id, "assistant", assistant_content)
    return {"response": assistant_content}
