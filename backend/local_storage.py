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
    
    def get_document_status(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document status and basic metadata from Supabase"""
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

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and all associated data (rows, anomalies, notes)."""
        pass

    def set_investee_name(self, document_id: str, investee_name: str) -> bool:
        """Set or update investee_name for a document."""
        pass

    def get_unique_investees(self) -> List[Dict[str, Any]]:
        """Get list of unique investees with last upload date."""
        pass

    def get_investee_full_context(self, investee_name: str) -> Dict[str, Any]:
        """Get full context for an investee (documents, rows, anomalies)."""
        pass

    def save_dashboard(self, investee_name: str, dashboard_name: str, spec: Dict[str, Any]) -> str:
        """Save a dashboard configuration. Returns dashboard_id."""
        pass

    def get_dashboards(self, investee_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all dashboards, optionally filtered by investee."""
        pass

    def get_dashboard(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Get a single dashboard by ID."""
        pass

    def get_reports(self, investee_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all reports, optionally filtered by investee."""
        pass

    def save_conversation_message(self, deal_id: str, role: str, content: str) -> Dict[str, Any]:
        """Save a user or assistant message for Ask Parity (deal-scoped)."""
        pass

    def get_conversation_messages(self, deal_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get last N messages for a deal, oldest first (chronological). Max 8–10 in prompt context."""
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
            logger.info(f"Inserting deal into Supabase: {deal_data.get('id')}")
            logger.info(f"Deal created_by: {deal_data.get('created_by')}")
            
            result = self.supabase.table('deals').insert(deal_data).execute()
            
            logger.info(f"Supabase insert result: {len(result.data) if result.data else 0} rows returned")
            
            if result.data and len(result.data) > 0:
                logger.info(f"Deal created successfully: {result.data[0].get('id')}")
                return result.data[0]
            else:
                logger.error("Supabase insert returned no data")
                return None
        except Exception as e:
            logger.error(f"Error creating deal: {e}", exc_info=True)
            logger.error(f"Deal data: {deal_data}")
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
            logger.info(f"Querying deals table for user_id: {user_id}")
            result = self.supabase.table('deals').select('*').eq('created_by', user_id).execute()
            logger.info(f"Query returned {len(result.data) if result.data else 0} deals")
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting deals for user {user_id}: {e}", exc_info=True)
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
            payload = {'deal_id': deal_id, **file_data}
            if 'upload_date' not in payload and 'uploaded_at' not in payload:
                payload['uploaded_at'] = datetime.utcnow().isoformat()
            result = self.supabase.table('evidence').insert(payload).execute()
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
                result = self.supabase.table('judgments').update(judgment_data).eq('id', existing['id']).execute()
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
        """Get document metadata from Supabase by ID"""
        try:
            result = self.supabase.table('documents')\
                .select('*')\
                .eq('id', document_id)\
                .single()\
                .execute()
            
            if hasattr(result, 'data') and result.data:
                return result.data
            return None
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None
    
    def get_document_status(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document status and basic metadata from Supabase"""
        try:
            result = self.supabase.table('documents')\
                .select('id, status, rows_count, error_message, error_code, created_at, updated_at')\
                .eq('id', document_id)\
                .single()\
                .execute()
            
            if hasattr(result, 'data') and result.data:
                return result.data
            return None
        except Exception as e:
            logger.error(f"Error getting status for document {document_id}: {e}")
            return None
    
    def store_document(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store a new document"""
        try:
            result = self.supabase.table('documents').insert(document_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error storing document: {e}")
            raise
    
    def update_document_status(
        self,
        document_id: str,
        status: Optional[str] = None,
        rows_count: Optional[int] = None,
        error_message: Optional[str] = None,
        anomalies_count: Optional[int] = None,
        insights_summary: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update document processing status and optional fields."""
        try:
            update_data = {}
            if status is not None:
                update_data['status'] = status
            if rows_count is not None:
                update_data['rows_count'] = rows_count
            if error_message is not None:
                update_data['error_message'] = error_message
            if anomalies_count is not None:
                update_data['anomalies_count'] = anomalies_count
            if insights_summary is not None:
                update_data['insights_summary'] = insights_summary
            if not update_data:
                return True
            update_data['updated_at'] = datetime.utcnow().isoformat()
            result = self.supabase.table('documents').update(update_data).eq('id', document_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error updating document status {document_id}: {e}")
            return False
    
    def store_rows(self, document_id: str, rows: List[Dict[str, Any]]) -> int:
        """Store extracted rows for a document. Accepts list of dicts (parser output) or list of {row_index, raw_json}."""
        try:
            self.supabase.table('extracted_rows').delete().eq('document_id', document_id).execute()
            # Normalize: parser returns list of dicts; DB expects row_index and raw_json
            normalized = []
            for i, row in enumerate(rows):
                if 'raw_json' in row and 'row_index' in row:
                    normalized.append({'document_id': document_id, 'row_index': row['row_index'], 'raw_json': row['raw_json']})
                else:
                    normalized.append({'document_id': document_id, 'row_index': i, 'raw_json': row})
            if not normalized:
                return 0
            result = self.supabase.table('extracted_rows').insert(normalized).execute()
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
        """Get insights for a document (from document.insights_summary if no insights table)."""
        try:
            doc = self.get_document(document_id)
            if doc and doc.get('insights_summary'):
                return doc['insights_summary']
            try:
                result = self.supabase.table('insights').select('*').eq('document_id', document_id).execute()
                return result.data[0].get('insights') if result.data else None
            except Exception:
                return None
        except Exception as e:
            logger.error(f"Error getting insights for document {document_id}: {e}")
            return None

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and all associated data (rows, anomalies)."""
        try:
            self.supabase.table('extracted_rows').delete().eq('document_id', document_id).execute()
            self.supabase.table('anomalies').delete().eq('document_id', document_id).execute()
            try:
                self.supabase.table('notes').delete().eq('document_id', document_id).execute()
            except Exception:
                pass
            self.supabase.table('documents').delete().eq('id', document_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            raise

    def set_investee_name(self, document_id: str, investee_name: str) -> bool:
        """Set or update investee_name for a document."""
        try:
            result = self.supabase.table('documents').update({
                'investee_name': investee_name,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', document_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting investee name for document {document_id}: {e}")
            return False

    def get_unique_investees(self) -> List[Dict[str, Any]]:
        """Get list of unique investees with last upload date from documents."""
        try:
            result = self.supabase.table('documents').select('investee_name, upload_date, id').not_.is_('investee_name', 'null').execute()
            by_name: Dict[str, Dict[str, Any]] = {}
            for row in (result.data or []):
                name = (row.get('investee_name') or '').strip()
                if not name:
                    continue
                if name not in by_name or (row.get('upload_date') or '') > (by_name[name].get('upload_date') or ''):
                    by_name[name] = {'investee_name': name, 'last_upload': row.get('upload_date'), 'document_id': row.get('id')}
            return list(by_name.values())
        except Exception as e:
            logger.error(f"Error getting unique investees: {e}")
            return []

    def get_investee_full_context(self, investee_name: str) -> Dict[str, Any]:
        """Get full context for an investee (documents, rows count, anomalies count)."""
        try:
            result = self.supabase.table('documents').select('*').eq('investee_name', investee_name).order('upload_date', desc=True).execute()
            docs = result.data or []
            doc_ids = [d['id'] for d in docs]
            total_rows = 0
            total_anomalies = 0
            for d in docs:
                total_rows += d.get('rows_count') or 0
                total_anomalies += d.get('anomalies_count') or 0
            return {
                'investee_name': investee_name,
                'documents': docs,
                'documents_count': len(docs),
                'total_rows': total_rows,
                'total_anomalies': total_anomalies,
            }
        except Exception as e:
            logger.error(f"Error getting investee context for {investee_name}: {e}")
            raise

    def save_dashboard(self, investee_name: str, dashboard_name: str, spec: Dict[str, Any]) -> str:
        """Save a dashboard configuration. Returns dashboard_id."""
        try:
            dashboard_id = str(uuid.uuid4())
            self.supabase.table('dashboards').insert({
                'id': dashboard_id,
                'investee_name': investee_name,
                'dashboard_name': dashboard_name,
                'spec': spec,
                'updated_at': datetime.utcnow().isoformat(),
            }).execute()
            return dashboard_id
        except Exception as e:
            logger.error(f"Error saving dashboard: {e}")
            raise

    def get_dashboards(self, investee_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all dashboards, optionally filtered by investee."""
        try:
            q = self.supabase.table('dashboards').select('*')
            if investee_name:
                q = q.eq('investee_name', investee_name)
            result = q.order('updated_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting dashboards: {e}")
            return []

    def get_dashboard(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Get a single dashboard by ID."""
        try:
            result = self.supabase.table('dashboards').select('*').eq('id', dashboard_id).single().execute()
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Error getting dashboard {dashboard_id}: {e}")
            return None

    def get_reports(self, investee_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all reports, optionally filtered by investee."""
        try:
            q = self.supabase.table('reports').select('*')
            if investee_name:
                q = q.eq('investee_name', investee_name)
            result = q.order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting reports: {e}")
            return []

    def save_conversation_message(self, deal_id: str, role: str, content: str) -> Dict[str, Any]:
        """Save a user or assistant message for Ask Parity (deal-scoped)."""
        try:
            row = {
                'deal_id': deal_id,
                'role': role,
                'content': content,
            }
            result = self.supabase.table('deal_conversations').insert(row).execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error saving conversation message for deal {deal_id}: {e}")
            raise

    def get_conversation_messages(self, deal_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get last N messages for a deal, oldest first (chronological). Max 8–10 in prompt context."""
        try:
            result = (
                self.supabase.table('deal_conversations')
                .select('*')
                .eq('deal_id', deal_id)
                .order('created_at', desc=True)
                .limit(limit)
                .execute()
            )
            rows = result.data or []
            rows.reverse()
            return rows
        except Exception as e:
            logger.error(f"Error getting conversation messages for deal {deal_id}: {e}")
            return []

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
