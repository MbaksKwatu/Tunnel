"""
FundIQ Backend Parser API
FastAPI server for parsing PDF, CSV, and XLSX files
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from parsers import get_parser

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
    title="FundIQ Parser API",
    description="Parse financial documents and extract structured data",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://caajasgudqsqlztjqedc.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNhYWphc2d1ZHFzcWx6dGpxZWRjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDAxOTIyNywiZXhwIjoyMDc1NTk1MjI3fQ.86MoLq3YsR9bPUSoJTZkAxrFHI2XWfGRMV8y68xpVX8"
)

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    logger.error("Missing Supabase credentials in environment variables")
    raise ValueError("Missing Supabase credentials")

# Create Supabase client with service_role key (bypasses RLS)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
logger.info("✅ [DEBUG] Supabase client initialized with SERVICE_ROLE key")
logger.info(f"✅ [DEBUG] Supabase URL: {SUPABASE_URL}")
logger.info(f"✅ [DEBUG] Service Role Key (first 20 chars): {SUPABASE_SERVICE_ROLE_KEY[:20]}...")


# Pydantic models
class ParseRequest(BaseModel):
    document_id: str = Field(..., description="Document ID from database")
    file_url: str = Field(..., description="URL of the file to parse")
    file_type: str = Field(..., description="File type: pdf, csv, or xlsx")


class ParseResponse(BaseModel):
    success: bool
    rows_extracted: int
    error: Optional[str] = None


# Helper functions
async def store_extracted_rows(document_id: str, rows: List[dict]) -> int:
    """Store extracted rows in Supabase"""
    try:
        logger.info(f"📥 [DEBUG] Storing {len(rows)} rows for document {document_id}")
        logger.info(f"📥 [DEBUG] Using Supabase service_role key for insert (bypasses RLS)")
        
        # Prepare data for insertion
        rows_to_insert = []
        for idx, row_data in enumerate(rows):
            rows_to_insert.append({
                'document_id': document_id,
                'row_index': idx,
                'raw_json': row_data
            })
        
        # Insert in batches of 1000 to avoid payload size limits
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(rows_to_insert), batch_size):
            batch = rows_to_insert[i:i + batch_size]
            logger.info(f"📤 [DEBUG] Inserting batch {i//batch_size + 1} into extracted_rows table...")
            result = supabase.table('extracted_rows').insert(batch).execute()
            logger.info(f"✅ [DEBUG] Batch insert response: {result}")
            total_inserted += len(batch)
            logger.info(f"✅ Inserted batch {i//batch_size + 1}: {len(batch)} rows")
        
        logger.info(f"✅ [DEBUG] Total rows inserted successfully: {total_inserted}")
        return total_inserted
        
    except Exception as e:
        logger.error(f"❌ [DEBUG] Error storing extracted rows: {e}")
        logger.error(f"❌ [DEBUG] Error type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ [DEBUG] Traceback: {traceback.format_exc()}")
        raise


async def update_document_status(
    document_id: str,
    status: str,
    rows_count: Optional[int] = None,
    error_message: Optional[str] = None
):
    """Update document status in Supabase"""
    try:
        update_data = {'status': status}
        if rows_count is not None:
            update_data['rows_count'] = rows_count
        if error_message is not None:
            update_data['error_message'] = error_message
        
        logger.info(f"📝 [DEBUG] Updating document {document_id} with data: {update_data}")
        logger.info(f"📝 [DEBUG] Using service_role key for update (bypasses RLS)")
        result = supabase.table('documents').update(update_data).eq('id', document_id).execute()
        logger.info(f"✅ [DEBUG] Update response: {result}")
        logger.info(f"✅ Updated document {document_id} status to {status}")
        
    except Exception as e:
        logger.error(f"❌ [DEBUG] Error updating document status: {e}")
        logger.error(f"❌ [DEBUG] Error type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ [DEBUG] Traceback: {traceback.format_exc()}")
        raise


async def process_document(document_id: str, file_url: str, file_type: str):
    """Process a document: parse and store extracted data"""
    try:
        logger.info(f"🚀 [DEBUG] ===== PROCESSING DOCUMENT =====")
        logger.info(f"🚀 [DEBUG] Document ID: {document_id}")
        logger.info(f"🚀 [DEBUG] File URL: {file_url}")
        logger.info(f"🚀 [DEBUG] File Type: {file_type}")
        logger.info(f"Processing document {document_id} ({file_type})")
        
        # Update status to processing
        await update_document_status(document_id, 'processing')
        
        # Get appropriate parser
        parser = get_parser(file_type)
        
        # Parse the file
        rows = await parser.parse(file_url)
        
        if not rows:
            logger.warning(f"No data extracted from document {document_id}")
            await update_document_status(
                document_id,
                'completed',
                rows_count=0,
                error_message='No data found in document'
            )
            return 0
        
        # Store extracted rows
        rows_inserted = await store_extracted_rows(document_id, rows)
        
        # Update document status to completed
        await update_document_status(document_id, 'completed', rows_count=rows_inserted)
        
        logger.info(f"Successfully processed document {document_id}: {rows_inserted} rows")
        return rows_inserted
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        # Update document status to failed
        await update_document_status(
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
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Test Supabase connection
        supabase.table('documents').select('id').limit(1).execute()
        supabase_status = "connected"
    except Exception as e:
        logger.error(f"Supabase health check failed: {e}")
        supabase_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "supabase": supabase_status,
        "parsers": ["pdf", "csv", "xlsx"]
    }


@app.post("/parse", response_model=ParseResponse)
async def parse_document(request: ParseRequest, background_tasks: BackgroundTasks):
    """
    Parse a document and extract structured data
    
    This endpoint accepts a document ID, file URL, and file type,
    then parses the file and stores the extracted data in the database.
    
    The parsing is done asynchronously to handle large files.
    """
    try:
        logger.info(f"📨 [DEBUG] ===== PARSE REQUEST RECEIVED =====")
        logger.info(f"📨 [DEBUG] Document ID: {request.document_id}")
        logger.info(f"📨 [DEBUG] File URL: {request.file_url}")
        logger.info(f"📨 [DEBUG] File Type: {request.file_type}")
        logger.info(f"Received parse request for document {request.document_id}")
        
        # Validate file type
        if request.file_type not in ['pdf', 'csv', 'xlsx']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {request.file_type}"
            )
        
        # Process the document (synchronously for now, but could be background task)
        rows_extracted = await process_document(
            request.document_id,
            request.file_url,
            request.file_type
        )
        
        return ParseResponse(
            success=True,
            rows_extracted=rows_extracted
        )
        
    except Exception as e:
        logger.error(f"Error in parse endpoint: {e}")
        return ParseResponse(
            success=False,
            rows_extracted=0,
            error=str(e)
        )


@app.get("/document/{document_id}")
async def get_document_info(document_id: str):
    """Get information about a document"""
    try:
        result = supabase.table('documents').select('*').eq('id', document_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Error fetching document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/document/{document_id}/rows")
async def get_document_rows(document_id: str, limit: int = 100, offset: int = 0):
    """Get extracted rows for a document"""
    try:
        result = (
            supabase.table('extracted_rows')
            .select('*')
            .eq('document_id', document_id)
            .order('row_index')
            .range(offset, offset + limit - 1)
            .execute()
        )
        
        return {
            "document_id": document_id,
            "rows": result.data,
            "count": len(result.data)
        }
        
    except Exception as e:
        logger.error(f"Error fetching document rows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


