"""
Parity Backend Parser API
FastAPI server for parsing PDF, CSV, and XLSX files with anomaly detection
AI-native financial intelligence for SME investments
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
import os
import time
import uuid
import json
import datetime
from dotenv import load_dotenv
from parsers import get_parser, PasswordRequiredError

# Import new modules
from local_storage import get_storage, StorageInterface, SQLiteStorage
from anomaly_engine import AnomalyDetector
from unsupervised_engine import UnsupervisedAnomalyDetector
from notes_manager import NotesManager
from insight_generator import InsightGenerator
from debug_logger import debug_logger
from report_generator import ReportGenerator

from evaluate_engine import Evaluator

# Import Parity AI Routes
import custom_report
from routes import dashboard_mutation, llm_actions

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Parity Parser API",
    description="Parse financial documents and extract structured data with anomaly detection",
    version="2.0.0"
)

# CORS middleware - configure allowed origins from environment
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Parity AI Routers
app.include_router(custom_report.router)
app.include_router(dashboard_mutation.router)
app.include_router(llm_actions.router)

# Initialize storage (Supabase or SQLite fallback)
storage: StorageInterface = get_storage()
logger.info(f"✅ Storage initialized: {type(storage).__name__}")

# Initialize anomaly detector
anomaly_detector = AnomalyDetector()
unsupervised_detector = UnsupervisedAnomalyDetector()

# Initialize notes manager
notes_manager = NotesManager()

# Initialize insight generator
insight_generator = InsightGenerator()

# Initialize report generator
report_generator = ReportGenerator()

# Initialize evaluator
evaluator = Evaluator()


# ==================== HELPER FUNCTIONS ====================

def detect_investee_name(rows: List[Dict[str, Any]], filename: str) -> str:
    """
    Detect investee/company name from parsed data or filename.
    Priority:
    1. Company name field in data
    2. Business name in header
    3. Filename without extension
    """
    if not rows:
        # Fallback to filename
        return filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    # Check first few rows for company-related fields
    company_keywords = ['company', 'business', 'name', 'organization', 'entity', 'client', 'investee']
    
    for row in rows[:5]:  # Check first 5 rows
        for key, value in row.items():
            key_lower = key.lower()
            if any(kw in key_lower for kw in company_keywords):
                if value and isinstance(value, str) and len(value.strip()) > 2:
                    return value.strip()
    
    # Check for common header patterns
    first_row = rows[0] if rows else {}
    for key, value in first_row.items():
        # Look for values that look like company names (capitalized, not too long)
        if isinstance(value, str) and len(value) > 3 and len(value) < 100:
            # Check if it looks like a company name (starts with capital, contains letters)
            if value[0].isupper() and any(c.isalpha() for c in value):
                # Avoid dates, numbers, common headers
                if not any(x in value.lower() for x in ['date', 'amount', 'total', 'balance', '/', '-']):
                    return value.strip()
    
    # Fallback to filename
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    # Clean up common patterns
    name = name.replace('_', ' ').replace('-', ' ')
    # Remove common suffixes
    for suffix in ['statement', 'report', 'data', 'export', 'transactions']:
        name = name.lower().replace(suffix, '').strip()
    
    return name.title() if name else "Unknown Company"


# Pydantic models
class ParseRequest(BaseModel):
    document_id: str = Field(..., description="Document ID from database")
    file_url: str = Field(..., description="URL of the file to parse")
    file_type: str = Field(..., description="File type: pdf, csv, or xlsx")
    password: Optional[str] = Field(None, description="Password for encrypted files")


class ParseResponse(BaseModel):
    success: bool
    rows_extracted: int
    anomalies_count: int = 0
    insights_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    document_id: Optional[str] = None
    investee_name_suggested: Optional[str] = None


class SetInvesteeRequest(BaseModel):
    investee_name: str = Field(..., description="Investee/company name")


class SaveDashboardRequest(BaseModel):
    investee_name: str = Field(..., description="Investee name")
    dashboard_name: str = Field(..., description="Dashboard name")
    spec: Dict[str, Any] = Field(..., description="Dashboard specification JSON")


class NoteCreate(BaseModel):
    content: str = Field(..., description="Note content")
    author: str = Field(default="system", description="Note author")


class AnalyzeRequest(BaseModel):
    document_id: str = Field(..., description="Document ID to analyze")


# Helper functions
async def process_document(document_id: str, file_url: str, file_type: str, password: Optional[str] = None):
    """Process a document: parse, store data, detect anomalies, generate insights"""
    parse_start_time = time.time()
    
    try:
        debug_logger.log_parse_start(document_id, file_type)
        logger.info(f"Processing document {document_id} ({file_type})")
        
        # Update status to processing
        storage.update_document_status(document_id, 'processing')
        
        # Get appropriate parser
        parser = get_parser(file_type)
        
        # Parse the file
        rows = await parser.parse(file_url, password=password)
        
        if not rows:
            logger.warning(f"No data extracted from document {document_id}")
            storage.update_document_status(
                document_id,
                'completed',
                rows_count=0,
                error_message='No data found in document'
            )
            return 0, [], None
        
        # Store extracted rows
        rows_inserted = storage.store_rows(document_id, rows)
        parse_time = time.time() - parse_start_time
        debug_logger.log_parse_complete(document_id, rows_inserted, parse_time)
        
        # Run anomaly detection
        detection_start_time = time.time()
        anomalies = anomaly_detector.detect_all(rows)
        detection_time = time.time() - detection_start_time
        
        # Log individual anomalies
        for anomaly in anomalies:
            debug_logger.log_anomaly(
                anomaly.get('anomaly_type'),
                anomaly.get('severity'),
                anomaly.get('description'),
                anomaly.get('row_index', -1)
            )
        
        # Store anomalies
        anomalies_count = 0
        if anomalies:
            anomalies_count = storage.store_anomalies(document_id, anomalies)
        
        debug_logger.log_anomaly_detection(document_id, anomalies_count, detection_time)
        
        # Generate insights
        insights = insight_generator.generate_insights(anomalies)
        debug_logger.log_insight_generation(document_id, len(insights.get('insights', [])))
        
        # Update document status with anomalies and insights
        storage.update_document_status(
            document_id,
            'completed',
            rows_count=rows_inserted,
            anomalies_count=anomalies_count,
            insights_summary=insights
        )
        
        logger.info(f"Successfully processed document {document_id}: {rows_inserted} rows, {anomalies_count} anomalies")
        return rows_inserted, anomalies, insights
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        debug_logger.log_error("PROCESS", e, {"document_id": document_id, "file_type": file_type})
        # Update document status to failed
        storage.update_document_status(
            document_id,
            'failed',
            error_message=str(e)
        )
        raise


# API Routes
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "FundIQ Parser API",
        "status": "running",
        "version": "2.0.0",
        "storage": type(storage).__name__
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Test storage connection
        test_doc = storage.get_document("test-non-existent-id")
        storage_status = "connected"
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        storage_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "storage": storage_status,
        "storage_type": type(storage).__name__,
        "parsers": ["pdf", "csv", "xlsx"]
    }


@app.post("/parse")
async def parse_document(
    request: Optional[ParseRequest] = None,
    file: Optional[UploadFile] = File(None),
    password: Optional[str] = Form(None)
):
    """
    Parse a document and extract structured data with anomaly detection
    
    This endpoint supports two modes:
    1. Direct file upload (local-first): POST with multipart/form-data file
    2. Supabase mode: POST with JSON containing document_id, file_url, file_type
    """
    document_id = None  # Track document ID for error handling
    try:
        # Check if direct file upload (local-first mode)
        if file:
            logger.info(f"📨 Direct file upload: {file.filename}")
            debug_logger.log_upload(file.filename, file.filename.split('.')[-1], file.size, "new")
            
            # Read file content
            file_content = await file.read()
            file_type = file.filename.split('.')[-1].lower()
            
            if file_type not in ['pdf', 'csv', 'xlsx']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_type}"
                )
            
            # Create document record
            document_id = str(uuid.uuid4())
            document_data = {
                'id': document_id,
                'user_id': 'demo-user',
                'file_name': file.filename,
                'file_type': file_type,
                'file_url': None,
                'status': 'processing'
            }
            storage.store_document(document_data)
            
            # Save file temporarily (or process directly)
            parser = get_parser(file_type)
            try:
                rows = await parser.parse(file_url=None, file_content=file_content, password=password)
            except PasswordRequiredError:
                raise # Re-raise to be caught by outer block
            except Exception as e:
                logger.error(f"Parser error: {e}")
                raise ValueError(f"Failed to parse file: {str(e)}")
            
            if not rows:
                storage.update_document_status(document_id, 'completed', rows_count=0, error_message='No data found')
                investee_suggested = detect_investee_name([], file.filename)
                return ParseResponse(
                    success=True, 
                    rows_extracted=0, 
                    anomalies_count=0,
                    document_id=document_id,
                    investee_name_suggested=investee_suggested
                )
            
            # Detect investee name from parsed data
            investee_suggested = detect_investee_name(rows, file.filename)
            logger.info(f"📋 Detected investee name: {investee_suggested}")
            
            # Store rows
            rows_inserted = storage.store_rows(document_id, rows)
            
            # Run anomaly detection
            anomalies = anomaly_detector.detect_all(rows)
            anomalies_count = 0
            if anomalies:
                anomalies_count = storage.store_anomalies(document_id, anomalies)
            
            # Generate insights
            insights = insight_generator.generate_insights(anomalies)
            
            # Update document with suggested investee name
            storage.update_document_status(
                document_id,
                'completed',
                rows_count=rows_inserted,
                anomalies_count=anomalies_count,
                insights_summary=insights
            )
            
            # Also set the suggested investee name on the document
            storage.set_investee_name(document_id, investee_suggested)
            
            return ParseResponse(
                success=True,
                rows_extracted=rows_inserted,
                anomalies_count=anomalies_count,
                insights_summary=insights,
                error=None,
                document_id=document_id,
                investee_name_suggested=investee_suggested
            )
        
        # Supabase mode: existing flow
        if not request:
            raise HTTPException(status_code=400, detail="Either file upload or parse request required")
        
        logger.info(f"📨 Parse request received for document {request.document_id}")
        
        # Validate file type
        if request.file_type not in ['pdf', 'csv', 'xlsx']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {request.file_type}"
            )
        
        # Process the document
        rows_extracted, anomalies, insights = await process_document(
            request.document_id,
            request.file_url,
            request.file_type,
            request.password
        )
        
        return ParseResponse(
            success=True,
            rows_extracted=rows_extracted,
            anomalies_count=len(anomalies) if anomalies else 0,
            insights_summary=insights
        )
        
    except PasswordRequiredError:
        logger.warning(f"Password required for document {request.document_id if request else document_id}")
        return ParseResponse(
            success=False,
            rows_extracted=0,
            anomalies_count=0,
            error="PASSWORD_REQUIRED"
        )
        
    except Exception as e:
        logger.error(f"Error in parse endpoint: {e}")
        debug_logger.log_error("PARSE", e, {"filename": file.filename if file else None})
        
        # Update document status to 'failed' if document was created
        if document_id:
            try:
                storage.update_document_status(
                    document_id,
                    'failed',
                    error_message=str(e)
                )
                logger.info(f"✅ Updated document {document_id} status to 'failed'")
            except Exception as update_error:
                logger.error(f"Failed to update document status: {update_error}")
        
        return ParseResponse(
            success=False,
            rows_extracted=0,
            anomalies_count=0,
            error=str(e)
        )


@app.post("/analyze")
async def analyze_document(request: AnalyzeRequest):
    """Re-run anomaly detection on an existing document"""
    try:
        # Get document rows
        rows_data = storage.get_rows(request.document_id, limit=10000)
        if not rows_data:
            raise HTTPException(status_code=404, detail="Document not found or has no rows")
        
        # Extract raw_json from rows
        rows = [row['raw_json'] for row in rows_data]
        
        # Run anomaly detection
        detection_start_time = time.time()
        anomalies = anomaly_detector.detect_all(rows)
        detection_time = time.time() - detection_start_time
        
        # Store anomalies
        anomalies_count = 0
        if anomalies:
            anomalies_count = storage.store_anomalies(request.document_id, anomalies)
        
        # Generate insights
        insights = insight_generator.generate_insights(anomalies)
        
        # Update document
        storage.update_document_status(
            request.document_id,
            None,  # Don't change status
            anomalies_count=anomalies_count,
            insights_summary=insights
        )
        
        return {
            "success": True,
            "anomalies_count": anomalies_count,
            "anomalies": anomalies[:100],  # Limit to first 100 for response
            "insights": insights,
            "detection_time": detection_time
        }
        
    except Exception as e:
        logger.error(f"Error in analyze endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def get_all_documents():
    """Get all documents (for local mode)"""
    try:
        # Use storage interface to get documents
        # For SQLite, query directly
        if isinstance(storage, SQLiteStorage):
            import sqlite3
            db_path = storage.db_path
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, user_id, file_name, file_type, file_url, format_detected,
                       upload_date, status, rows_count, anomalies_count, error_message,
                       insights_summary, created_at, updated_at
                FROM documents
                ORDER BY upload_date DESC
            """)
            
            documents = []
            for row in cursor.fetchall():
                doc = {
                    'id': row[0],
                    'user_id': row[1],
                    'file_name': row[2],
                    'file_type': row[3],
                    'file_url': row[4],
                    'format_detected': row[5],
                    'upload_date': row[6] or '',
                    'status': row[7],
                    'rows_count': row[8] or 0,
                    'anomalies_count': row[9] or 0,
                    'error_message': row[10],
                    'insights_summary': json.loads(row[11]) if row[11] else None,
                    'created_at': row[12] or '',
                    'updated_at': row[13] or ''
                }
                documents.append(doc)
            
            conn.close()
            return documents
        else:
            # For Supabase, use storage methods
            # Return empty for now - would need to implement get_all in storage interface
            return []
        
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


@app.get("/document/{document_id}")
async def get_document_info(document_id: str):
    """Get information about a document"""
    try:
        doc = storage.get_document(document_id)
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return doc
        
    except Exception as e:
        logger.error(f"Error fetching document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/document/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its associated data"""
    try:
        doc = storage.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete document (cascades to rows, anomalies, notes via foreign keys)
        storage.delete_document(document_id)
        
        logger.info(f"✅ Deleted document {document_id}")
        return {"success": True, "message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/document/{document_id}/rows")
async def get_document_rows(document_id: str, limit: int = 100, offset: int = 0):
    """Get extracted rows for a document"""
    try:
        rows = storage.get_rows(document_id, limit=limit, offset=offset)
        
        return {
            "document_id": document_id,
            "rows": rows,
            "count": len(rows)
        }
        
    except Exception as e:
        logger.error(f"Error fetching document rows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/document/{document_id}/anomalies")
async def get_document_anomalies(document_id: str):
    """Get all anomalies for a document"""
    try:
        anomalies = storage.get_anomalies(document_id)
        return {
            "document_id": document_id,
            "anomalies": anomalies,
            "count": len(anomalies)
        }
    except Exception as e:
        logger.error(f"Error fetching anomalies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/anomalies")
async def get_anomalies_by_query(doc_id: str):
    """Alias endpoint: Get anomalies by document ID via query param"""
    return await get_document_anomalies(doc_id)


@app.post("/api/anomalies/run")
async def rerun_anomaly_detection(request: AnalyzeRequest):
    """Alias endpoint: Re-run anomaly detection"""
    return await analyze_document(request)


@app.post("/api/documents/{doc_id}/detect")
async def detect_anomalies_endpoint(doc_id: str):
    """
    Run unsupervised anomaly detection (Isolation Forest / LOF) on a document.
    """
    try:
        logger.info(f"Running unsupervised detection for document {doc_id}")
        
        # 1. Load parsed rows
        rows_data = storage.get_rows(doc_id, limit=100000) # Get all rows
        if not rows_data:
            raise HTTPException(status_code=404, detail="Document not found or has no rows")
            
        rows = [row['raw_json'] for row in rows_data]
        
        # 2. Run detection
        result = unsupervised_detector.detect(rows)
        anomalies = result.get('anomalies', [])
        
        # 3. Store anomalies
        # For MVP, we store in DB as usual, but also write to JSON file as requested
        if anomalies:
            storage.store_anomalies(doc_id, anomalies)
            
            # Write to JSON file
            os.makedirs("anomalies", exist_ok=True)
            file_path = f"anomalies/{doc_id}.json"
            with open(file_path, 'w') as f:
                json.dump(anomalies, f, indent=2)
            logger.info(f"Saved anomalies to {file_path}")
            
        return result
        
    except Exception as e:
        logger.error(f"Error in detection endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/document/{document_id}/evaluate")
async def evaluate_document(document_id: str):
    """Calculate financial metrics for a document"""
    try:
        # Get rows
        rows_data = storage.get_rows(document_id, limit=100000)
        if not rows_data:
             return {"metrics": []}
             
        rows = [row['raw_json'] for row in rows_data]
        return evaluator.evaluate(rows)
    except Exception as e:
        logger.error(f"Error evaluating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/document/{document_id}/report")
async def generate_ic_report(document_id: str):
    """Generate and download IC Report PDF"""
    try:
        # Fetch all data
        doc = storage.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        rows_data = storage.get_rows(document_id, limit=100000)
        rows = [row['raw_json'] for row in rows_data]
        
        anomalies = storage.get_anomalies(document_id)
        notes = notes_manager.get_all_notes(document_id)
        
        # Get insights (or generate if missing)
        insights = doc.get('insights_summary')
        if not insights:
            insights = insight_generator.generate_insights(anomalies)
            
        # Calculate metrics
        metrics_result = evaluator.evaluate(rows)
        metrics = metrics_result.get('metrics', [])
        
        # Generate Report
        # Use original filename or fallback
        doc_name = doc.get('file_name', f"doc_{document_id}")
        filename = f"{doc_name}_IC_Report.pdf"
        
        filepath = report_generator.generate_report(
            document_id,
            doc_name,
            insights,
            anomalies,
            notes,
            metrics=metrics,
            rows_sample=rows_data
        )
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/document/{document_id}/insights")
async def get_document_insights(document_id: str):
    """Get generated insights for a document"""
    try:
        doc = storage.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        insights = doc.get('insights_summary')
        if not insights:
            # Generate insights if not present
            anomalies = storage.get_anomalies(document_id)
            insights = insight_generator.generate_insights(anomalies)
        
        return insights
    except Exception as e:
        logger.error(f"Error fetching insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Notes endpoints
@app.get("/document/{document_id}/notes")
async def get_document_notes(document_id: str):
    """Get all notes for a document"""
    try:
        notes = notes_manager.get_all_notes(document_id)
        return {
            "document_id": document_id,
            "notes": notes,
            "count": len(notes)
        }
    except Exception as e:
        logger.error(f"Error fetching notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/document/{document_id}/notes")
async def create_document_note(document_id: str, note: NoteCreate):
    """Create a document-level note"""
    try:
        new_note = notes_manager.create_note(
            document_id=document_id,
            content=note.content,
            author=note.author
        )
        return new_note
    except Exception as e:
        logger.error(f"Error creating note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AnomalyNoteCreate(BaseModel):
    content: str = Field(..., description="Note content")
    author: str = Field(default="system", description="Note author")
    document_id: str = Field(..., description="Document ID")


@app.post("/anomalies/{anomaly_id}/notes")
async def create_anomaly_note(anomaly_id: str, note: AnomalyNoteCreate):
    """Create a note for a specific anomaly"""
    try:
        new_note = notes_manager.create_note(
            document_id=note.document_id,
            content=note.content,
            author=note.author,
            anomaly_id=anomaly_id
        )
        return new_note
    except Exception as e:
        logger.error(f"Error creating anomaly note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/notes/{note_id}/replies")
async def get_note_replies(note_id: str, document_id: str):
    """Get replies to a note"""
    try:
        replies = notes_manager.get_note_replies(document_id, note_id)
        return {
            "note_id": note_id,
            "replies": replies,
            "count": len(replies)
        }
    except Exception as e:
        logger.error(f"Error fetching note replies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/logs")
async def get_debug_logs(lines: int = 100):
    """Get recent debug logs"""
    try:
        logs = debug_logger.get_recent_logs(lines)
        return {
            "logs": logs,
            "lines": lines
        }
    except Exception as e:
        logger.error(f"Error fetching debug logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/document/{document_id}/cancel")
async def cancel_processing(document_id: str):
    """Cancel processing for a document"""
    try:
        doc = storage.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc.get('status') != 'processing':
            raise HTTPException(status_code=400, detail="Document is not processing")
        
        # Update status to cancelled
        storage.update_document_status(
            document_id,
            'failed',
            error_message='Processing cancelled by user'
        )
        
        logger.info(f"✅ Cancelled processing for document {document_id}")
        return {"success": True, "message": "Processing cancelled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/document/{document_id}/retry")
async def retry_processing(document_id: str):
    """Retry processing for a failed document"""
    try:
        doc = storage.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc.get('status') not in ['failed']:
            raise HTTPException(status_code=400, detail="Can only retry failed documents")
        
        # Reset status to processing
        storage.update_document_status(
            document_id,
            'processing',
            error_message=None
        )
        
        # Note: Actual reprocessing would require the original file
        # For now, this just resets the status
        # In production, you'd queue the file for reprocessing
        
        logger.info(f"✅ Retrying processing for document {document_id}")
        return {
            "success": True, 
            "message": "Status reset to processing",
            "note": "Re-upload the file to actually reprocess it"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cleanup/stuck-files")
async def cleanup_stuck_files(max_age_minutes: int = 30):
    """Cleanup files stuck in processing status"""
    try:
        if isinstance(storage, SQLiteStorage):
            import sqlite3
            db_path = storage.db_path
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Find documents stuck in processing for more than max_age_minutes
            cursor.execute("""
                UPDATE documents 
                SET status = 'failed', 
                    error_message = 'Processing timeout - file may have been corrupted or too large',
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing' 
                  AND datetime(created_at, '+' || ? || ' minutes') < datetime('now')
            """, (max_age_minutes,))
            
            updated_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Cleaned up {updated_count} stuck files")
            return {
                "success": True,
                "updated_count": updated_count,
                "message": f"Marked {updated_count} stuck files as failed"
            }
        else:
            return {"success": False, "message": "Cleanup only supported for SQLite storage"}
            
    except Exception as e:
        logger.error(f"Error cleaning up stuck files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/report")
async def generate_ic_report_endpoint(doc_id: str):
    """Generate Investment Committee PDF report"""
    try:
        logger.info(f"Generating IC report for document {doc_id}")
        
        # Fetch document data
        document = storage.get_document(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Fetch anomalies
        anomalies = storage.get_anomalies(doc_id)
        
        # Fetch rows (limited sample)
        rows = storage.get_rows(doc_id, limit=10000)
        
        # Fetch notes
        try:
            notes = notes_manager.get_all_notes(doc_id).get('notes', [])
        except:
            notes = []
        
        # Generate insights
        insights = insight_generator.generate_insights(anomalies)
        
        # Generate PDF report
        report_path = report_generator.generate_report(
            document_id=doc_id,
            document_name=document.get('file_name', 'Unknown'),
            insights=insights,
            anomalies=anomalies,
            notes=notes,
            rows_sample=rows[:50] if rows else None
        )
        
        logger.info(f"Report generated successfully: {report_path}")
        
        # Return file
        return FileResponse(
            report_path,
            media_type='application/pdf',
            filename=f"{document.get('file_name', 'document')}_IC_Report.pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating IC report: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ==================== INVESTEE ENDPOINTS ====================

@app.post("/documents/{document_id}/set-investee")
async def set_investee(document_id: str, body: SetInvesteeRequest):
    """Set or update the investee name for a document"""
    try:
        doc = storage.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        storage.set_investee_name(document_id, body.investee_name)
        logger.info(f"✅ Set investee name for {document_id}: {body.investee_name}")
        
        return {"status": "ok", "investee_name": body.investee_name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting investee name: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/investees")
async def list_investees():
    """Get list of unique investees with last upload date"""
    try:
        investees = storage.get_unique_investees()
        return investees
    except Exception as e:
        logger.error(f"Error fetching investees: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/investees/{investee_name}/full")
async def get_investee_full_context(investee_name: str):
    """Get full context for an investee (all documents, rows, anomalies, analysis)"""
    try:
        context = storage.get_investee_full_context(investee_name)
        return context
    except Exception as e:
        logger.error(f"Error fetching investee context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DASHBOARD ENDPOINTS ====================

@app.post("/dashboards/save")
async def save_dashboard(data: SaveDashboardRequest):
    """Save a dashboard configuration"""
    try:
        dashboard_id = storage.save_dashboard(
            investee_name=data.investee_name,
            dashboard_name=data.dashboard_name,
            spec=data.spec
        )
        logger.info(f"✅ Saved dashboard {dashboard_id} for {data.investee_name}")
        
        return {"status": "ok", "dashboard_id": dashboard_id}
        
    except Exception as e:
        logger.error(f"Error saving dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboards")
async def list_dashboards(investee_name: Optional[str] = None):
    """Get all dashboards, optionally filtered by investee"""
    try:
        dashboards = storage.get_dashboards(investee_name)
        return dashboards
    except Exception as e:
        logger.error(f"Error fetching dashboards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    """Get a single dashboard by ID"""
    try:
        dashboard = storage.get_dashboard(dashboard_id)
        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return dashboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== REPORT LISTING ENDPOINT ====================

@app.get("/reports")
async def list_reports(investee_name: Optional[str] = None):
    """Get all reports, optionally filtered by investee"""
    try:
        reports = storage.get_reports(investee_name)
        return reports
    except Exception as e:
        logger.error(f"Error fetching reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
