"""
Storage abstraction layer for Parity MVP
Supports both Supabase and SQLite with automatic fallback
"""
import sqlite3
import json
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class StorageInterface:
    """Abstract storage interface"""
    
    def store_document(self, document_data: Dict[str, Any]) -> str:
        """Store document and return document_id"""
        raise NotImplementedError
    
    def store_rows(self, document_id: str, rows: List[Dict[str, Any]]) -> int:
        """Store extracted rows and return count"""
        raise NotImplementedError
    
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        raise NotImplementedError
    
    def get_rows(self, document_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get extracted rows for document"""
        raise NotImplementedError
    
    def update_document_status(
        self, 
        document_id: str, 
        status: str, 
        rows_count: Optional[int] = None,
        error_message: Optional[str] = None,
        anomalies_count: Optional[int] = None,
        insights_summary: Optional[Dict[str, Any]] = None
    ):
        """Update document status"""
        raise NotImplementedError
    
    def store_anomalies(self, document_id: str, anomalies: List[Dict[str, Any]]) -> int:
        """Store anomalies for document"""
        raise NotImplementedError
    
    def get_anomalies(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all anomalies for document"""
        raise NotImplementedError
    
    def delete_document(self, document_id: str):
        """Delete a document and all associated data"""
        raise NotImplementedError


class SQLiteStorage(StorageInterface):
    """SQLite-based storage implementation"""
    
    def __init__(self, db_path: str = "fundiq_local.db"):
        self.db_path = db_path
        self.init_db()
        logger.info(f"✅ SQLite storage initialized at {db_path}")
    
    def init_db(self):
        """Initialize SQLite database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_url TEXT,
                format_detected TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'uploaded',
                rows_count INTEGER DEFAULT 0,
                anomalies_count INTEGER DEFAULT 0,
                error_message TEXT,
                insights_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create extracted_rows table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extracted_rows (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                raw_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
                UNIQUE(document_id, row_index)
            )
        """)
        
        # Create anomalies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                row_index INTEGER,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                score REAL,
                suggested_action TEXT,
                metadata TEXT,
                raw_json TEXT,
                evidence TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_rows_document_id ON extracted_rows(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_document_id ON anomalies(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies(anomaly_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity)")
        
        conn.commit()
        conn.close()
        
        # Run migrations
        self._migrate_anomalies_table()
        
        return True

    def _migrate_anomalies_table(self):
        """Add new columns to anomalies table if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check existing columns
            cursor.execute("PRAGMA table_info(anomalies)")
            columns = [info[1] for info in cursor.fetchall()]
            
            new_columns = {
                'score': 'REAL',
                'suggested_action': 'TEXT',
                'metadata': 'TEXT'
            }
            
            for col, dtype in new_columns.items():
                if col not in columns:
                    logger.info(f"Migrating anomalies table: adding {col}")
                    cursor.execute(f"ALTER TABLE anomalies ADD COLUMN {col} {dtype}")
            
            conn.commit()
        except Exception as e:
            logger.error(f"Migration failed: {e}")
        finally:
            conn.close()
    
    def store_document(self, document_data: Dict[str, Any]) -> str:
        """Store document and return document_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Generate UUID if not provided
        document_id = document_data.get('id') or str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO documents (
                id, user_id, file_name, file_type, file_url, 
                format_detected, status, rows_count, anomalies_count, 
                insights_summary, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            document_data.get('user_id'),
            document_data.get('file_name'),
            document_data.get('file_type'),
            document_data.get('file_url'),
            document_data.get('format_detected'),
            document_data.get('status', 'uploaded'),
            document_data.get('rows_count', 0),
            document_data.get('anomalies_count', 0),
            json.dumps(document_data.get('insights_summary')) if document_data.get('insights_summary') else None,
            document_data.get('error_message')
        ))
        
        conn.commit()
        conn.close()
        return document_id
    
    def store_rows(self, document_id: str, rows: List[Dict[str, Any]]) -> int:
        """Store extracted rows and return count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        rows_to_insert = []
        for idx, row_data in enumerate(rows):
            rows_to_insert.append((
                str(uuid.uuid4()),
                document_id,
                idx,
                json.dumps(row_data)
            ))
        
        cursor.executemany("""
            INSERT OR REPLACE INTO extracted_rows (id, document_id, row_index, raw_json)
            VALUES (?, ?, ?, ?)
        """, rows_to_insert)
        
        conn.commit()
        conn.close()
        return len(rows)
    
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # Map row to dict
        columns = [desc[0] for desc in cursor.description]
        doc = dict(zip(columns, row))
        
        # Parse JSON fields
        if doc.get('insights_summary'):
            try:
                doc['insights_summary'] = json.loads(doc['insights_summary'])
            except:
                doc['insights_summary'] = None
        
        return doc
    
    def get_rows(self, document_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get extracted rows for document"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT row_index, raw_json
            FROM extracted_rows
            WHERE document_id = ?
            ORDER BY row_index
            LIMIT ? OFFSET ?
        """, (document_id, limit, offset))
        
        rows = []
        for row in cursor.fetchall():
            rows.append({
                'row_index': row[0],
                'raw_json': json.loads(row[1])
            })
        
        conn.close()
        return rows
    
    def update_document_status(
        self, 
        document_id: str, 
        status: str, 
        rows_count: Optional[int] = None,
        error_message: Optional[str] = None,
        anomalies_count: Optional[int] = None,
        insights_summary: Optional[Dict[str, Any]] = None
    ):
        """Update document status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = ['status = ?']
        params = [status]
        
        if rows_count is not None:
            updates.append('rows_count = ?')
            params.append(rows_count)
        
        if anomalies_count is not None:
            updates.append('anomalies_count = ?')
            params.append(anomalies_count)
        
        if error_message is not None:
            updates.append('error_message = ?')
            params.append(error_message)
        
        if insights_summary is not None:
            updates.append('insights_summary = ?')
            params.append(json.dumps(insights_summary))
        
        updates.append('updated_at = CURRENT_TIMESTAMP')
        params.append(document_id)
        
        cursor.execute(f"""
            UPDATE documents 
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)
        
        conn.commit()
        conn.close()
    
    def store_anomalies(self, document_id: str, anomalies: List[Dict[str, Any]]) -> int:
        """Store anomalies for document"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        anomalies_to_insert = []
        for anomaly in anomalies:
            anomalies_to_insert.append((
                str(uuid.uuid4()),
                document_id,
                anomaly.get('row_index'),
                anomaly.get('anomaly_type'),
                anomaly.get('severity'),
                anomaly.get('description'),
                anomaly.get('score'),
                anomaly.get('suggested_action'),
                json.dumps(anomaly.get('metadata')) if anomaly.get('metadata') else None,
                json.dumps(anomaly.get('raw_json')) if anomaly.get('raw_json') else None,
                json.dumps(anomaly.get('evidence')) if anomaly.get('evidence') else None
            ))
        
        cursor.executemany("""
            INSERT INTO anomalies (
                id, document_id, row_index, anomaly_type, severity,
                description, score, suggested_action, metadata, raw_json, evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, anomalies_to_insert)
        
        conn.commit()
        conn.close()
        
        # Update document anomalies_count
        self.update_document_status(document_id, None, anomalies_count=len(anomalies))
        
        return len(anomalies)
    
    def get_anomalies(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all anomalies for document"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, document_id, row_index, anomaly_type, severity,
                   description, score, suggested_action, metadata, raw_json, evidence, detected_at
            FROM anomalies
            WHERE document_id = ?
            ORDER BY severity DESC, detected_at DESC
        """, (document_id,))
        
        anomalies = []
        for row in cursor.fetchall():
            anomaly = {
                'id': row[0],
                'document_id': row[1],
                'row_index': row[2],
                'anomaly_type': row[3],
                'severity': row[4],
                'description': row[5],
                'score': row[6],
                'suggested_action': row[7],
                'metadata': json.loads(row[8]) if row[8] else None,
                'raw_json': json.loads(row[9]) if row[9] else None,
                'evidence': json.loads(row[10]) if row[10] else None,
                'detected_at': row[11]
            }
            anomalies.append(anomaly)
        
        conn.close()
        return anomalies
    
    def delete_document(self, document_id: str):
        """Delete a document and all associated data (cascades via foreign keys)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete document - foreign keys will cascade delete rows, anomalies, and notes
        cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Deleted document {document_id} and associated data")


class SupabaseStorage(StorageInterface):
    """Supabase-based storage implementation"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        logger.info("✅ Supabase storage initialized")
    
    def store_document(self, document_data: Dict[str, Any]) -> str:
        """Store document and return document_id"""
        result = self.supabase.table('documents').insert(document_data).execute()
        return result.data[0]['id']
    
    def store_rows(self, document_id: str, rows: List[Dict[str, Any]]) -> int:
        """Store extracted rows and return count"""
        rows_to_insert = []
        for idx, row_data in enumerate(rows):
            rows_to_insert.append({
                'document_id': document_id,
                'row_index': idx,
                'raw_json': row_data
            })
        
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(rows_to_insert), batch_size):
            batch = rows_to_insert[i:i + batch_size]
            self.supabase.table('extracted_rows').insert(batch).execute()
            total_inserted += len(batch)
        
        return total_inserted
    
    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        result = self.supabase.table('documents').select('*').eq('id', document_id).execute()
        return result.data[0] if result.data else None
    
    def get_rows(self, document_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get extracted rows for document"""
        result = (
            self.supabase.table('extracted_rows')
            .select('*')
            .eq('document_id', document_id)
            .order('row_index')
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data
    
    def update_document_status(
        self, 
        document_id: str, 
        status: str, 
        rows_count: Optional[int] = None,
        error_message: Optional[str] = None,
        anomalies_count: Optional[int] = None,
        insights_summary: Optional[Dict[str, Any]] = None
    ):
        """Update document status"""
        update_data = {}
        
        if status:
            update_data['status'] = status
        if rows_count is not None:
            update_data['rows_count'] = rows_count
        if anomalies_count is not None:
            update_data['anomalies_count'] = anomalies_count
        if error_message is not None:
            update_data['error_message'] = error_message
        if insights_summary is not None:
            update_data['insights_summary'] = insights_summary
        
        self.supabase.table('documents').update(update_data).eq('id', document_id).execute()
    
    def store_anomalies(self, document_id: str, anomalies: List[Dict[str, Any]]) -> int:
        """Store anomalies for document"""
        try:
            # Prepare data for Supabase
            anomalies_to_insert = []
            for anomaly in anomalies:
                anomalies_to_insert.append({
                    'document_id': document_id,
                    'row_index': anomaly.get('row_index'),
                    'anomaly_type': anomaly.get('anomaly_type'),
                    'severity': anomaly.get('severity'),
                    'description': anomaly.get('description'),
                    'score': anomaly.get('score'),
                    'suggested_action': anomaly.get('suggested_action'),
                    'metadata': anomaly.get('metadata'),  # Supabase handles JSON automatically if column is JSONB
                    'raw_json': anomaly.get('raw_json'),
                    'evidence': anomaly.get('evidence')
                })
            
            # Batch insert
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(anomalies_to_insert), batch_size):
                batch = anomalies_to_insert[i:i + batch_size]
                self.supabase.table('anomalies').insert(batch).execute()
                total_inserted += len(batch)
            
            # Update document anomalies_count
            self.update_document_status(document_id, None, anomalies_count=len(anomalies))
            
            return total_inserted
            
        except Exception as e:
            logger.error(f"Error storing anomalies in Supabase: {e}")
            # Fallback to SQLite? Or raise? 
            # If Supabase fails, we might want to know. But for hybrid, maybe fallback.
            # Given the request asks to 'Add Supabase optional support', if it fails here, 
            # it implies Supabase IS configured but failing.
            # I'll log and re-raise to ensure we don't silently lose data if the intent was Supabase.
            raise e
    
    def get_anomalies(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all anomalies for document"""
        try:
            result = (
                self.supabase.table('anomalies')
                .select('*')
                .eq('document_id', document_id)
                .order('severity', ascending=False)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"Error getting anomalies from Supabase: {e}")
            raise e
    
    def delete_document(self, document_id: str):
        """Delete a document and all associated data"""
        # Delete from Supabase tables
        # Note: Supabase doesn't have cascade delete by default, so we need to delete manually
        try:
            # Delete anomalies first
            self.supabase.table('anomalies').delete().eq('document_id', document_id).execute()
            
            # Delete extracted rows
            self.supabase.table('extracted_rows').delete().eq('document_id', document_id).execute()
            
            # Delete notes
            self.supabase.table('notes').delete().eq('document_id', document_id).execute()
            
            # Finally delete the document
            self.supabase.table('documents').delete().eq('id', document_id).execute()
            
            logger.info(f"✅ Deleted document {document_id} from Supabase")
        except Exception as e:
            logger.error(f"Error deleting document from Supabase: {e}")
            raise


def get_storage() -> StorageInterface:
    """Get storage instance with automatic Supabase/SQLite detection"""
    try:
        from supabase import create_client
        import os
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if supabase_url and supabase_key:
            try:
                supabase_client = create_client(supabase_url, supabase_key)
                # Test connection
                supabase_client.table('documents').select('id').limit(1).execute()
                logger.info("✅ Using Supabase storage")
                return SupabaseStorage(supabase_client)
            except Exception as e:
                logger.warning(f"Supabase connection failed: {e}, falling back to SQLite")
        
        logger.info("✅ Using SQLite storage (local-first)")
        return SQLiteStorage()
        
    except ImportError:
        logger.info("✅ Using SQLite storage (Supabase not available)")
        return SQLiteStorage()

