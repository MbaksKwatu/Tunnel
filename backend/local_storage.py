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
        status: Optional[str], 
        rows_count: Optional[int] = None,
        rows_parsed: Optional[int] = None,
        rows_expected: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        next_action: Optional[str] = None,
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
    """SQLite-based storage implementation for Parity"""
    
    def __init__(self, db_path: str = "parity_local.db"):
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
                investee_name TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'uploaded',
                rows_count INTEGER DEFAULT 0,
                rows_parsed INTEGER DEFAULT 0,
                rows_expected INTEGER,
                anomalies_count INTEGER DEFAULT 0,
                error_code TEXT,
                error_message TEXT,
                next_action TEXT,
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
        
        # Create dashboards table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dashboards (
                id TEXT PRIMARY KEY,
                investee_name TEXT NOT NULL,
                dashboard_name TEXT NOT NULL,
                spec TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                investee_name TEXT NOT NULL,
                report_name TEXT NOT NULL,
                report_type TEXT DEFAULT 'ic_report',
                dashboard_spec TEXT,
                storage_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create analysis_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                analysis_type TEXT NOT NULL,
                results TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_investee ON documents(investee_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_rows_document_id ON extracted_rows(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_document_id ON anomalies(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies(anomaly_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dashboards_investee ON dashboards(investee_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_investee ON reports(investee_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_document ON analysis_results(document_id)")
        
        conn.commit()
        conn.close()
        
        # Run migrations
        self._migrate_anomalies_table()
        self._migrate_documents_table()
        
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
    
    def _migrate_documents_table(self):
        """Add missing columns to documents table if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("PRAGMA table_info(documents)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if 'investee_name' not in columns:
                logger.info("Migrating documents table: adding investee_name")
                cursor.execute("ALTER TABLE documents ADD COLUMN investee_name TEXT")

            if 'rows_parsed' not in columns:
                logger.info("Migrating documents table: adding rows_parsed")
                cursor.execute("ALTER TABLE documents ADD COLUMN rows_parsed INTEGER DEFAULT 0")

            if 'rows_expected' not in columns:
                logger.info("Migrating documents table: adding rows_expected")
                cursor.execute("ALTER TABLE documents ADD COLUMN rows_expected INTEGER")

            if 'error_code' not in columns:
                logger.info("Migrating documents table: adding error_code")
                cursor.execute("ALTER TABLE documents ADD COLUMN error_code TEXT")

            if 'next_action' not in columns:
                logger.info("Migrating documents table: adding next_action")
                cursor.execute("ALTER TABLE documents ADD COLUMN next_action TEXT")
            
            conn.commit()
        except Exception as e:
            logger.error(f"Documents migration failed: {e}")
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
                format_detected, investee_name, status, rows_count, rows_parsed, rows_expected,
                anomalies_count, error_code, error_message, next_action,
                insights_summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            document_data.get('user_id'),
            document_data.get('file_name'),
            document_data.get('file_type'),
            document_data.get('file_url'),
            document_data.get('format_detected'),
            document_data.get('investee_name'),
            document_data.get('status', 'uploaded'),
            document_data.get('rows_count', 0),
            document_data.get('rows_parsed', 0),
            document_data.get('rows_expected'),
            document_data.get('anomalies_count', 0),
            document_data.get('error_code'),
            document_data.get('error_message'),
            document_data.get('next_action'),
            json.dumps(document_data.get('insights_summary')) if document_data.get('insights_summary') else None
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
        status: Optional[str], 
        rows_count: Optional[int] = None,
        rows_parsed: Optional[int] = None,
        rows_expected: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        next_action: Optional[str] = None,
        anomalies_count: Optional[int] = None,
        insights_summary: Optional[Dict[str, Any]] = None
    ):
        """Update document status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates: List[str] = []
        params: List[Any] = []

        if status is not None:
            updates.append('status = ?')
            params.append(status)
        
        if rows_count is not None:
            updates.append('rows_count = ?')
            params.append(rows_count)

        if rows_parsed is not None:
            updates.append('rows_parsed = ?')
            params.append(rows_parsed)

        if rows_expected is not None:
            updates.append('rows_expected = ?')
            params.append(rows_expected)

        if anomalies_count is not None:
            updates.append('anomalies_count = ?')
            params.append(anomalies_count)
        if error_message is not None:
            updates.append('error_message = ?')
            params.append(error_message)

        if error_code is not None:
            updates.append('error_code = ?')
            params.append(error_code)

        if next_action is not None:
            updates.append('next_action = ?')
            params.append(next_action)
        
        if insights_summary is not None:
            updates.append('insights_summary = ?')
            params.append(json.dumps(insights_summary))
        
        if not updates:
            conn.close()
            return

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
    
    # ==================== INVESTEE METHODS ====================
    
    def set_investee_name(self, document_id: str, investee_name: str):
        """Set investee name for a document"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE documents SET investee_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (investee_name, document_id)
        )
        conn.commit()
        conn.close()
    
    def get_unique_investees(self) -> List[Dict[str, Any]]:
        """Get list of unique investees with last upload date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT investee_name, MAX(created_at) as last_uploaded
            FROM documents
            WHERE investee_name IS NOT NULL AND investee_name != ''
            GROUP BY investee_name
            ORDER BY last_uploaded DESC
        """)
        
        investees = []
        for row in cursor.fetchall():
            investees.append({
                'investee_name': row[0],
                'last_uploaded': row[1]
            })
        
        conn.close()
        return investees
    
    def get_investee_full_context(self, investee_name: str) -> Dict[str, Any]:
        """Get full context for an investee (all docs, rows, anomalies, analysis)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all documents for this investee
        cursor.execute(
            "SELECT * FROM documents WHERE investee_name = ?",
            (investee_name,)
        )
        columns = [desc[0] for desc in cursor.description]
        docs = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        doc_ids = [d['id'] for d in docs]
        
        if not doc_ids:
            conn.close()
            return {'documents': [], 'rows': [], 'anomalies': [], 'analysis': []}
        
        placeholders = ','.join(['?' for _ in doc_ids])
        
        # Get all rows
        cursor.execute(f"""
            SELECT document_id, row_index, raw_json
            FROM extracted_rows
            WHERE document_id IN ({placeholders})
        """, doc_ids)
        rows = []
        for row in cursor.fetchall():
            rows.append({
                'document_id': row[0],
                'row_index': row[1],
                'raw_json': json.loads(row[2]) if row[2] else {}
            })
        
        # Get all anomalies
        cursor.execute(f"""
            SELECT * FROM anomalies WHERE document_id IN ({placeholders})
        """, doc_ids)
        anomaly_cols = [desc[0] for desc in cursor.description]
        anomalies = [dict(zip(anomaly_cols, row)) for row in cursor.fetchall()]
        
        # Get all analysis results
        cursor.execute(f"""
            SELECT * FROM analysis_results WHERE document_id IN ({placeholders})
        """, doc_ids)
        analysis_cols = [desc[0] for desc in cursor.description]
        analysis = [dict(zip(analysis_cols, row)) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'documents': docs,
            'rows': rows,
            'anomalies': anomalies,
            'analysis': analysis
        }
    
    # ==================== DASHBOARD METHODS ====================
    
    def save_dashboard(self, investee_name: str, dashboard_name: str, spec: Dict[str, Any]) -> str:
        """Save a dashboard configuration"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        dashboard_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO dashboards (id, investee_name, dashboard_name, spec)
            VALUES (?, ?, ?, ?)
        """, (dashboard_id, investee_name, dashboard_name, json.dumps(spec)))
        
        conn.commit()
        conn.close()
        return dashboard_id
    
    def get_dashboards(self, investee_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all dashboards, optionally filtered by investee"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if investee_name:
            cursor.execute(
                "SELECT * FROM dashboards WHERE investee_name = ? ORDER BY created_at DESC",
                (investee_name,)
            )
        else:
            cursor.execute("SELECT * FROM dashboards ORDER BY created_at DESC")
        
        columns = [desc[0] for desc in cursor.description]
        dashboards = []
        for row in cursor.fetchall():
            d = dict(zip(columns, row))
            if d.get('spec'):
                d['spec'] = json.loads(d['spec'])
            dashboards.append(d)
        
        conn.close()
        return dashboards
    
    def get_dashboard(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Get a single dashboard by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dashboards WHERE id = ?", (dashboard_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        d = dict(zip(columns, row))
        if d.get('spec'):
            d['spec'] = json.loads(d['spec'])
        return d
    
    # ==================== REPORT METHODS ====================
    
    def save_report(self, investee_name: str, report_name: str, report_type: str = 'ic_report',
                    dashboard_spec: Optional[Dict] = None, storage_path: Optional[str] = None) -> str:
        """Save a report record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        report_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO reports (id, investee_name, report_name, report_type, dashboard_spec, storage_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            report_id, investee_name, report_name, report_type,
            json.dumps(dashboard_spec) if dashboard_spec else None,
            storage_path
        ))
        
        conn.commit()
        conn.close()
        return report_id
    
    def get_reports(self, investee_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all reports, optionally filtered by investee"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if investee_name:
            cursor.execute(
                "SELECT * FROM reports WHERE investee_name = ? ORDER BY created_at DESC",
                (investee_name,)
            )
        else:
            cursor.execute("SELECT * FROM reports ORDER BY created_at DESC")
        
        columns = [desc[0] for desc in cursor.description]
        reports = []
        for row in cursor.fetchall():
            r = dict(zip(columns, row))
            if r.get('dashboard_spec'):
                r['dashboard_spec'] = json.loads(r['dashboard_spec'])
            reports.append(r)
        
        conn.close()
        return reports
    
    # ==================== ANALYSIS METHODS ====================
    
    def save_analysis(self, document_id: str, analysis_type: str, results: Dict[str, Any]) -> str:
        """Save analysis results for a document"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        analysis_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO analysis_results (id, document_id, analysis_type, results)
            VALUES (?, ?, ?, ?)
        """, (analysis_id, document_id, analysis_type, json.dumps(results)))
        
        conn.commit()
        conn.close()
        return analysis_id
    
    def get_analysis(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all analysis results for a document"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM analysis_results WHERE document_id = ? ORDER BY created_at DESC",
            (document_id,)
        )
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            r = dict(zip(columns, row))
            if r.get('results'):
                r['results'] = json.loads(r['results'])
            results.append(r)
        
        conn.close()
        return results


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
        status: Optional[str], 
        rows_count: Optional[int] = None,
        rows_parsed: Optional[int] = None,
        rows_expected: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        next_action: Optional[str] = None,
        anomalies_count: Optional[int] = None,
        insights_summary: Optional[Dict[str, Any]] = None
    ):
        """Update document status"""
        update_data: Dict[str, Any] = {}

        if status is not None:
            update_data['status'] = status
        if rows_count is not None:
            update_data['rows_count'] = rows_count
        if rows_parsed is not None:
            update_data['rows_parsed'] = rows_parsed
        if rows_expected is not None:
            update_data['rows_expected'] = rows_expected
        if anomalies_count is not None:
            update_data['anomalies_count'] = anomalies_count
        if error_code is not None:
            update_data['error_code'] = error_code
        if error_message is not None:
            update_data['error_message'] = error_message
        if next_action is not None:
            update_data['next_action'] = next_action
        if insights_summary is not None:
            update_data['insights_summary'] = insights_summary

        if not update_data:
            return

        try:
            self.supabase.table('documents').update(update_data).eq('id', document_id).execute()
        except Exception as e:
            logger.warning(f"Document status update failed (likely schema mismatch): {e}")
            safe_update_data: Dict[str, Any] = {}
            if status is not None:
                safe_update_data['status'] = status
            if rows_count is not None:
                safe_update_data['rows_count'] = rows_count
            if anomalies_count is not None:
                safe_update_data['anomalies_count'] = anomalies_count
            if error_message is not None:
                safe_update_data['error_message'] = error_message
            if insights_summary is not None:
                safe_update_data['insights_summary'] = insights_summary
            if safe_update_data:
                self.supabase.table('documents').update(safe_update_data).eq('id', document_id).execute()
    
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
            return result.data or []
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
    
    # ==================== INVESTEE METHODS ====================
    
    def set_investee_name(self, document_id: str, investee_name: str):
        """Set investee name for a document"""
        try:
            self.supabase.table('documents').update({'investee_name': investee_name}).eq('id', document_id).execute()
        except Exception as e:
            logger.warning(f"Skipping investee_name update (likely missing column): {e}")
    
    def get_unique_investees(self) -> List[Dict[str, Any]]:
        """Get list of unique investees with last upload date"""
        try:
            result = self.supabase.table('documents').select('investee_name, created_at').execute()
        except Exception as e:
            logger.warning(f"Skipping get_unique_investees (likely missing column): {e}")
            return []
        
        unique = {}
        for row in result.data:
            name = row.get('investee_name')
            if name and name not in unique:
                unique[name] = row['created_at']
            elif name and row['created_at'] > unique[name]:
                unique[name] = row['created_at']
        
        return [{'investee_name': k, 'last_uploaded': v} for k, v in unique.items()]
    
    def get_investee_full_context(self, investee_name: str) -> Dict[str, Any]:
        """Get full context for an investee"""
        try:
            docs = self.supabase.table('documents').select('*').eq('investee_name', investee_name).execute().data
        except Exception as e:
            logger.warning(f"Skipping get_investee_full_context (likely missing column): {e}")
            return {'documents': [], 'rows': [], 'anomalies': [], 'analysis': []}
        doc_ids = [d['id'] for d in docs]
        
        if not doc_ids:
            return {'documents': [], 'rows': [], 'anomalies': [], 'analysis': []}
        
        rows = self.supabase.table('extracted_rows').select('*').in_('document_id', doc_ids).execute().data
        anomalies = self.supabase.table('anomalies').select('*').in_('document_id', doc_ids).execute().data
        analysis = self.supabase.table('analysis_results').select('*').in_('document_id', doc_ids).execute().data
        
        return {
            'documents': docs,
            'rows': rows,
            'anomalies': anomalies,
            'analysis': analysis
        }
    
    # ==================== DASHBOARD METHODS ====================
    
    def save_dashboard(self, investee_name: str, dashboard_name: str, spec: Dict[str, Any]) -> str:
        """Save a dashboard configuration"""
        result = self.supabase.table('dashboards').insert({
            'investee_name': investee_name,
            'dashboard_name': dashboard_name,
            'spec': spec
        }).execute()
        return result.data[0]['id']
    
    def get_dashboards(self, investee_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all dashboards, optionally filtered by investee"""
        query = self.supabase.table('dashboards').select('*').order('created_at', desc=True)
        if investee_name:
            query = query.eq('investee_name', investee_name)
        return query.execute().data
    
    def get_dashboard(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Get a single dashboard by ID"""
        result = self.supabase.table('dashboards').select('*').eq('id', dashboard_id).execute()
        return result.data[0] if result.data else None
    
    # ==================== REPORT METHODS ====================
    
    def save_report(self, investee_name: str, report_name: str, report_type: str = 'ic_report',
                    dashboard_spec: Optional[Dict] = None, storage_path: Optional[str] = None) -> str:
        """Save a report record"""
        result = self.supabase.table('reports').insert({
            'investee_name': investee_name,
            'report_name': report_name,
            'report_type': report_type,
            'dashboard_spec': dashboard_spec,
            'storage_path': storage_path
        }).execute()
        return result.data[0]['id']
    
    def get_reports(self, investee_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all reports, optionally filtered by investee"""
        query = self.supabase.table('reports').select('*').order('created_at', desc=True)
        if investee_name:
            query = query.eq('investee_name', investee_name)
        return query.execute().data
    
    # ==================== ANALYSIS METHODS ====================
    
    def save_analysis(self, document_id: str, analysis_type: str, results: Dict[str, Any]) -> str:
        """Save analysis results for a document"""
        result = self.supabase.table('analysis_results').insert({
            'document_id': document_id,
            'analysis_type': analysis_type,
            'results': results
        }).execute()
        return result.data[0]['id']
    
    def get_analysis(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all analysis results for a document"""
        return self.supabase.table('analysis_results').select('*').eq('document_id', document_id).order('created_at', desc=True).execute().data


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

