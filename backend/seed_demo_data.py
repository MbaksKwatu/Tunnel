import os
import sys
import json
import uuid
from datetime import datetime
from local_storage import get_storage

def seed_data():
    print("🌱 Seeding Demo Data...")
    storage = get_storage()
    
    # Check if any document exists
    # We'll check by trying to get all docs. 
    # Since get_document requires ID, we'll access the db directly for check or assume if we don't know any ID.
    # But local_storage.py doesn't have list_documents. 
    # We will just insert one unconditionally or catch unique constraint if we hardcode ID.

    demo_doc_id = "demo-doc-123"
    
    try:
        # Attempt to clean up previous demo data if exists (requires implementing delete in storage or raw SQL)
        # Since delete_document is in interface but might not be implemented fully or we want a quick fix:
        import sqlite3
        if isinstance(storage, sqlite3.Connection) or hasattr(storage, 'db_path'):
             conn = sqlite3.connect(storage.db_path)
             cursor = conn.cursor()
             cursor.execute("DELETE FROM documents WHERE id = ?", (demo_doc_id,))
             cursor.execute("DELETE FROM extracted_rows WHERE document_id = ?", (demo_doc_id,))
             cursor.execute("DELETE FROM anomalies WHERE document_id = ?", (demo_doc_id,))
             conn.commit()
             conn.close()
             print("🧹 Cleaned up old demo data")
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")

    doc_data = {
        "id": demo_doc_id,
        "user_id": "12345678-1234-1234-1234-123456789abc",
        "file_name": "Financial Statements Q3.pdf",
        "file_type": "pdf",
        "file_url": "https://example.com/demo.pdf",
        "format_detected": "pdf",
        "upload_date": datetime.now().isoformat(),
        "status": "processed",
        "rows_count": 10,
        "anomalies_count": 2,
        "error_message": None,
        "insights_summary": json.dumps({"revenue_growth": "15%", "profit_margin": "22%"})
    }

    try:
        # Try to insert document
        storage.store_document(doc_data)
        print(f"✅ Inserted Document: {demo_doc_id}")

        # Insert Sample Rows
        rows = [
            {"row_index": 0, "raw_json": json.dumps({"Metric": "Revenue", "Q1": 100000, "Q2": 115000, "Q3": 130000})},
            {"row_index": 1, "raw_json": json.dumps({"Metric": "COGS", "Q1": 40000, "Q2": 45000, "Q3": 48000})},
            {"row_index": 2, "raw_json": json.dumps({"Metric": "OpEx", "Q1": 30000, "Q2": 32000, "Q3": 31000})}
        ]
        storage.store_rows(demo_doc_id, rows)
        print(f"✅ Inserted {len(rows)} Sample Rows")

        # Insert Sample Anomalies
        anomalies = [
             {
                "row_index": 1,
                "column": "Q2",
                "value": "45000",
                "reason": "Unexpected spike in COGS ratio",
                "severity": "medium",
                "score": 0.75,
                "suggested_action": "Review supplier contracts",
                "anomaly_type": "spike",
                "description": "Cost of Goods Sold increased disproportionately to revenue."
            },
            {
                "row_index": 2,
                "column": "Q3",
                "value": "31000",
                "reason": "Expense drop inconsistent with revenue growth",
                "severity": "low",
                "score": 0.45,
                "suggested_action": "Verify payroll data",
                "anomaly_type": "inconsistency",
                "description": "Operating expenses dropped while revenue grew."
            }
        ]
        storage.store_anomalies(demo_doc_id, anomalies)
        print(f"✅ Inserted {len(anomalies)} Sample Anomalies")

    except Exception as e:
        print(f"⚠️ Data might already exist or error: {e}")

if __name__ == "__main__":
    seed_data()
