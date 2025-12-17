import unittest
import random
import logging
import pandas as pd
import os
import shutil
from unsupervised_engine import UnsupervisedAnomalyDetector

# Configure logging
logging.basicConfig(level=logging.INFO)

class TestUnsupervisedAnomalyDetector(unittest.TestCase):
    
    def setUp(self):
        random.seed(42)
        self.detector = UnsupervisedAnomalyDetector({'ml_min_samples': 5})
        self.test_output_dir = "test_output"
        if not os.path.exists(self.test_output_dir):
            os.makedirs(self.test_output_dir)
            
    def generate_synthetic_data(self, n_rows=50, outlier_indices=None):
        rows = []
        outlier_indices = outlier_indices or []
        
        for i in range(n_rows):
            if i in outlier_indices:
                # Generate outlier
                row = {
                    'row_index': i,
                    'amount': random.uniform(100000, 500000),  # Huge amount
                    'count': random.randint(100, 200),
                    'description': f'Outlier transaction {i}'
                }
            else:
                # Generate normal data
                row = {
                    'row_index': i,
                    'amount': random.uniform(100, 1000),  # Normal amount
                    'count': random.randint(1, 10),
                    'description': f'Normal transaction {i}'
                }
            rows.append(row)
        return rows

    def save_to_csv(self, result, filename):
        # Save anomalies to CSV
        anomalies = result.get('anomalies', [])
        if anomalies:
            df = pd.DataFrame(anomalies)
            path = os.path.join(self.test_output_dir, filename)
            df.to_csv(path, index=False)
            print(f"Saved anomalies to {path}")
        else:
            print(f"No anomalies to save for {filename}")

    def test_isolation_forest_large_dataset(self):
        print("\nTesting Isolation Forest (N=60)...")
        # 3 outliers in 60 rows = 5%
        # Set contamination slightly higher to ensure detection
        detector = UnsupervisedAnomalyDetector({'ml_min_samples': 5, 'ml_contamination': 0.06})
        
        outlier_indices = [10, 30, 55]
        rows = self.generate_synthetic_data(n_rows=60, outlier_indices=outlier_indices)
        
        result = detector.detect(rows)
        anomalies = result['anomalies']
        
        print(f"Found {len(anomalies)} anomalies")
        for a in anomalies:
            meta = a.get('metadata') or {}
            algo = meta.get('algorithm')
            print(f"- Row {a['row_index']}: {a['description']} ({algo})")
            self.assertEqual(algo, 'isolation_forest')
            
        # Verify outliers detected
        detected_indices = [a['row_index'] for a in anomalies]
        for idx in outlier_indices:
            self.assertIn(idx, detected_indices, f"Failed to detect outlier {idx} with Isolation Forest")
            
        self.save_to_csv(result, 'test_isolation_anomalies.csv')

    def test_lof_small_dataset(self):
        print("\nTesting LOF (N=20)...")
        # 2 outliers in 20 rows = 10%
        # Set contamination higher
        detector = UnsupervisedAnomalyDetector({'ml_min_samples': 5, 'ml_contamination': 0.2})
        
        outlier_indices = [5, 15]
        rows = self.generate_synthetic_data(n_rows=20, outlier_indices=outlier_indices)
        
        # Debug data
        print("\nData Inspection:")
        for i in [3, 5, 7, 15, 18]:
            if i < len(rows):
                print(f"Row {i}: Amount={rows[i]['amount']}, Count={rows[i]['count']}")

        result = detector.detect(rows)
        anomalies = result['anomalies']
        
        print(f"Found {len(anomalies)} anomalies")
        for a in anomalies:
            meta = a.get('metadata') or {}
            algo = meta.get('algorithm')
            print(f"- Row {a['row_index']}: {a['description']} ({algo})")
            self.assertEqual(algo, 'lof')
            
        # Verify outliers detected
        detected_indices = [a['row_index'] for a in anomalies]
        for idx in outlier_indices:
            self.assertIn(idx, detected_indices, f"Failed to detect outlier {idx} with LOF")
            
        self.save_to_csv(result, 'test_lof_anomalies.csv')

if __name__ == '__main__':
    unittest.main()
