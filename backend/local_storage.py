import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class StorageInterface:
    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        pass
    
    def create_deal(self, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    def update_deal(self, deal_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass
    
    def get_deals_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all deals for a user"""
        pass
    
    def get_evidence_by_deal(self, deal_id: str) -> List[Dict[str, Any]]:
        """Get all evidence for a deal (alias for get_evidence)"""
        pass
    
    def delete_deal(self, deal_id: str) -> bool:
        pass
    
    def get_evidence(self, deal_id: str) -> List[Dict[str, Any]]:
        pass
    
    def add_evidence(self, deal_id: str, file_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    def get_judgment(self, deal_id: str) -> Optional[Dict[str, Any]]:
        pass
    
    def save_judgment(self, deal_id: str, judgment_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    # Document-related methods
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        pass
    
    def store_document(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store a new document"""
        pass
    
    def update_document_status(self, document_id: str, status: str, rows_count: Optional[int] = None, error_message: Optional[str] = None) -> bool:
        """Update document processing status"""
        pass
    
    def store_rows(self, document_id: str, rows: List[Dict[str, Any]]) -> int:
        """Store extracted rows for a document"""
        pass
    
    def get_rows(self, document_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get extracted rows for a document"""
        pass
    
    def store_anomalies(self, document_id: str, anomalies: List[Dict[str, Any]]) -> int:
        """Store detected anomalies for a document"""
        pass
    
    def get_anomalies(self, document_id: str) -> List[Dict[str, Any]]:
        """Get anomalies for a document"""
        pass
    
    def store_insights(self, document_id: str, insights: Dict[str, Any]) -> bool:
        """Store insights for a document"""
        pass
    
    def get_insights(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get insights for a document"""
        pass

class SupabaseStorage(StorageInterface):
    def __init__(self, supabase_client):
        self.supabase = supabase_client

    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.supabase.table('deals').select('*').eq('id', deal_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting deal {deal_id}: {e}")
            return None

    def create_deal(self, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self.supabase.table('deals').insert(deal_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating deal: {e}")
            raise

    def update_deal(self, deal_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            result = self.supabase.table('deals').update(update_data).eq('id', deal_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error updating deal {deal_id}: {e}")
            return None

    def get_deals_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all deals for a user"""
        try:
            result = self.supabase.table('deals').select('*').eq('created_by', user_id).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting deals for user {user_id}: {e}")
            return []
    
    def get_evidence_by_deal(self, deal_id: str) -> List[Dict[str, Any]]:
        """Get all evidence for a deal (alias for get_evidence)"""
        return self.get_evidence(deal_id)
    
    def delete_deal(self, deal_id: str) -> bool:
        """Delete a deal and all associated evidence/judgments"""
        try:
            # Delete evidence first (foreign key)
            self.supabase.table('evidence').delete().eq('deal_id', deal_id).execute()
            # Delete judgment
            self.supabase.table('judgments').delete().eq('deal_id', deal_id).execute()
            # Delete deal
            self.supabase.table('deals').delete().eq('id', deal_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting deal {deal_id}: {e}")
            return False

    def get_evidence(self, deal_id: str) -> List[Dict[str, Any]]:
        try:
            result = self.supabase.table('evidence').select('*').eq('deal_id', deal_id).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting evidence for deal {deal_id}: {e}")
            return []

    def add_evidence(self, deal_id: str, file_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self.supabase.table('evidence').insert({
                'deal_id': deal_id,
                **file_data,
                'upload_date': datetime.utcnow().isoformat()
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error adding evidence for deal {deal_id}: {e}")
            raise

    def get_judgment(self, deal_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.supabase.table('judgments').select('*').eq('deal_id', deal_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting judgment for deal {deal_id}: {e}")
            return None

    def save_judgment(self, deal_id: str, judgment_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Check if judgment exists
            existing = self.get_judgment(deal_id)
            
            if existing:
                # Update existing judgment
                result = self.supabase.table('judgments').update({
                    **judgment_data,
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', existing['id']).execute()
            else:
                # Create new judgment
                result = self.supabase.table('judgments').insert({
                    'id': str(uuid.uuid4()),
                    'deal_id': deal_id,
                    **judgment_data,
                    'created_at': datetime.utcnow().isoformat()
                }).execute()
                
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error saving judgment for deal {deal_id}: {e}")
            raise

    # Document-related methods
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        try:
            result = self.supabase.table('documents').select('*').eq('id', document_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None
    
    def store_document(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store a new document"""
        try:
            result = self.supabase.table('documents').insert(document_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error storing document: {e}")
            raise
    
    def update_document_status(self, document_id: str, status: str, rows_count: Optional[int] = None, error_message: Optional[str] = None) -> bool:
        """Update document processing status"""
        try:
            update_data = {'status': status}
            if rows_count is not None:
                update_data['rows_count'] = rows_count
            if error_message is not None:
                update_data['error_message'] = error_message
            
            result = self.supabase.table('documents').update(update_data).eq('id', document_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error updating document status {document_id}: {e}")
            return False
    
    def store_rows(self, document_id: str, rows: List[Dict[str, Any]]) -> int:
        """Store extracted rows for a document"""
        try:
            # Clear existing rows for this document
            self.supabase.table('extracted_rows').delete().eq('document_id', document_id).execute()
            
            # Insert new rows
            rows_with_doc_id = [{'document_id': document_id, **row} for row in rows]
            result = self.supabase.table('extracted_rows').insert(rows_with_doc_id).execute()
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"Error storing rows for document {document_id}: {e}")
            return 0
    
    def get_rows(self, document_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get extracted rows for a document"""
        try:
            result = self.supabase.table('extracted_rows').select('*').eq('document_id', document_id).range(offset, offset + limit - 1).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting rows for document {document_id}: {e}")
            return []
    
    def store_anomalies(self, document_id: str, anomalies: List[Dict[str, Any]]) -> int:
        """Store detected anomalies for a document"""
        try:
            # Clear existing anomalies for this document
            self.supabase.table('anomalies').delete().eq('document_id', document_id).execute()
            
            # Insert new anomalies
            anomalies_with_doc_id = [{'document_id': document_id, **anomaly} for anomaly in anomalies]
            result = self.supabase.table('anomalies').insert(anomalies_with_doc_id).execute()
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"Error storing anomalies for document {document_id}: {e}")
            return 0
    
    def get_anomalies(self, document_id: str) -> List[Dict[str, Any]]:
        """Get anomalies for a document"""
        try:
            result = self.supabase.table('anomalies').select('*').eq('document_id', document_id).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting anomalies for document {document_id}: {e}")
            return []
    
    def store_insights(self, document_id: str, insights: Dict[str, Any]) -> bool:
        """Store insights for a document"""
        try:
            result = self.supabase.table('insights').upsert({
                'document_id': document_id,
                'insights': insights,
                'updated_at': datetime.utcnow().isoformat()
            }).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error storing insights for document {document_id}: {e}")
            return False
    
    def get_insights(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get insights for a document"""
        try:
            result = self.supabase.table('insights').select('*').eq('document_id', document_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting insights for document {document_id}: {e}")
            return None

def get_storage() -> StorageInterface:
    """Get storage instance with Supabase"""
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Missing Supabase configuration. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")
            
        supabase_client = create_client(supabase_url, supabase_key)
        logger.info("✅ Using Supabase storage")
        return SupabaseStorage(supabase_client)
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase storage: {e}")
        raise
