"""
Unsupervised Anomaly Detection Engine
Uses Isolation Forest to detect outliers in financial data, with LOF fallback for small datasets.
"""
import logging
import numpy as np
import json
from typing import List, Dict, Any, Optional, Tuple
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

logger = logging.getLogger(__name__)

class UnsupervisedAnomalyDetector:
    """
    Detects anomalies using unsupervised machine learning.
    - > 50 rows: Isolation Forest
    - < 50 rows: Local Outlier Factor (LOF)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.contamination = self.config.get('ml_contamination', 0.03)  # Default 0.03 per requirement
        self.min_samples_if = 50  # Min rows for Isolation Forest
        self.random_state = 42
        
    def detect(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run unsupervised anomaly detection.
        Returns:
            {
                "scores": float array,
                "mask": boolean array (True=Anomaly),
                "anomalies": list of anomaly objects
            }
        """
        if not rows:
            return {"scores": [], "mask": [], "anomalies": []}
            
        try:
            # 1. Extract numeric features
            features, row_indices, feature_names = self._extract_features(rows)
            
            if not features:
                logger.warning("No numeric features found for ML detection")
                return {"scores": [], "mask": [], "anomalies": []}
                
            # 2. Preprocess data
            X = np.array(features)
            imputer = SimpleImputer(strategy='mean')
            X_imputed = imputer.fit_transform(X)
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_imputed)
            
            # 3. Choose Algorithm
            n_samples = len(rows)
            algorithm = "isolation_forest"
            
            if n_samples < self.min_samples_if:
                algorithm = "lof"
                # Use LOF for small datasets
                # Use fewer neighbors for better local sensitivity
                n_neighbors = min(5, max(1, n_samples - 1))
                clf = LocalOutlierFactor(
                    n_neighbors=n_neighbors,
                    contamination=self.contamination,
                    novelty=False # LOF for outlier detection (predict on X)
                )
                # fit_predict returns -1 for outliers, 1 for inliers
                predictions = clf.fit_predict(X_scaled)
                # negative_outlier_factor_ is the score (larger is better/inlier, smaller is outlier)
                scores = clf.negative_outlier_factor_
            else:
                # Use Isolation Forest for larger datasets
                clf = IsolationForest(
                    contamination=self.contamination,
                    random_state=self.random_state,
                    n_jobs=-1
                )
                predictions = clf.fit_predict(X_scaled)
                scores = clf.decision_function(X_scaled)

            # 4. Process results
            anomalies = []
            mask = (predictions == -1).tolist()
            scores_list = scores.tolist()
            
            # Determine severity thresholds based on percentiles of scores
            # Lower score = more anomalous
            try:
                high_thresh = np.percentile(scores, 2)   # Bottom 2% (most anomalous)
                medium_thresh = np.percentile(scores, 10) # Bottom 10%
            except:
                # Fallback for very small datasets
                high_thresh = -0.5
                medium_thresh = -0.1

            for i, is_anomaly in enumerate(mask):
                if is_anomaly:
                    row_idx = row_indices[i]
                    score = scores[i]
                    
                    # Identify key feature
                    row_scaled = X_scaled[i]
                    max_dev_idx = np.argmax(np.abs(row_scaled))
                    key_feature = feature_names[max_dev_idx]
                    key_value = X_imputed[i][max_dev_idx]
                    
                    # Assign severity by percentile
                    if score <= high_thresh:
                        severity = "HIGH"
                    elif score <= medium_thresh:
                        severity = "MEDIUM"
                    else:
                        severity = "LOW"
                    
                    anomalies.append({
                        "row_index": row_idx,
                        "anomaly_type": "unsupervised_outlier",
                        "score": float(score),
                        "severity": severity,
                        "description": f"Outlier detected by {algorithm.upper()}. Unusual {key_feature}: {key_value:.2f}",
                        "suggested_action": f"Verify {key_feature} value for accuracy.",
                        "metadata": {
                            "algorithm": algorithm,
                            "key_feature": key_feature,
                            "key_value": float(key_value),
                            "score_percentile": float(score)
                        }
                    })
            
            logger.info(f"{algorithm.upper()} found {len(anomalies)} anomalies in {n_samples} rows")
            
            return {
                "scores": scores_list,
                "mask": mask,
                "anomalies": anomalies
            }
            
        except Exception as e:
            logger.error(f"Error in unsupervised anomaly detection: {e}")
            return {"scores": [], "mask": [], "anomalies": [], "error": str(e)}

    def _extract_features(self, rows: List[Dict[str, Any]]):
        """Extract numeric values from rows."""
        # 1. Identify numeric fields
        numeric_fields = set()
        sample_size = min(len(rows), 50)
        
        for row in rows[:sample_size]:
            for key, value in row.items():
                if self._is_numeric(value) and key.lower() not in ['page', 'table', 'row_index', 'id', 'document_id']:
                    numeric_fields.add(key)
        
        feature_names = list(numeric_fields)
        if not feature_names:
            return [], [], []
            
        # 2. Build matrix
        features = []
        valid_indices = []
        
        for i, row in enumerate(rows):
            row_features = []
            has_data = False
            
            for field in feature_names:
                val = self._to_numeric(row.get(field))
                if val is not None:
                    row_features.append(val)
                    has_data = True
                else:
                    row_features.append(np.nan)
            
            if has_data:
                features.append(row_features)
                valid_indices.append(i)
                
        return features, valid_indices, feature_names

    def _is_numeric(self, value: Any) -> bool:
        if value is None: return False
        try:
            str_value = str(value).replace('$', '').replace(',', '').replace(' ', '')
            float(str_value)
            return True
        except:
            return False

    def _to_numeric(self, value: Any) -> Optional[float]:
        if value is None: return None
        try:
            str_value = str(value).replace('$', '').replace(',', '').replace(' ', '')
            return float(str_value)
        except:
            return None
