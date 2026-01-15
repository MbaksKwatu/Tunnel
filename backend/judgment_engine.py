from typing import Dict, List, Optional

# from models import Deal, Evidence, Thesis  # Removed: Supabase-only deployment


class JudgmentEngine:
    """
    Context-aware judgment engine for emerging market SME investments.
    Understands informality, governance gaps, data scarcity, and structural risks.
    """

    INFORMALITY_TOLERANCE = {
        "pre_revenue": {"max_acceptable": 80, "penalty_reduction": 0.3},
        "early_revenue": {"max_acceptable": 60, "penalty_reduction": 0.5},
        "growth": {"max_acceptable": 40, "penalty_reduction": 0.7},
        "mature": {"max_acceptable": 20, "penalty_reduction": 1.0},
    }

    STAGE_FINANCIAL_REQUIREMENTS = {
        "pre_revenue": ["bank_statements"],
        "early_revenue": ["bank_statements", "management_accounts"],
        "growth": ["audited_financials_or_management_accounts"],
        "mature": ["audited_financials_required"],
    }

    GEOGRAPHY_RISK_FACTORS = {
        "nigeria": {"fx_risk": 0.3, "infrastructure_risk": 0.2, "regulatory_risk": 0.25},
        "kenya": {"fx_risk": 0.15, "infrastructure_risk": 0.15, "regulatory_risk": 0.1},
        "south_africa": {"fx_risk": 0.2, "infrastructure_risk": 0.3, "regulatory_risk": 0.15},
        "ghana": {"fx_risk": 0.25, "infrastructure_risk": 0.2, "regulatory_risk": 0.2},
    }

    SECTOR_NORMS = {
        "fintech": {"typical_margin": 0.35, "license_critical": True, "data_quality_required": "high"},
        "logistics": {"typical_margin": 0.15, "license_critical": False, "data_quality_required": "medium"},
        "agritech": {"typical_margin": 0.20, "license_critical": False, "data_quality_required": "medium"},
        "healthcare": {"typical_margin": 0.25, "license_critical": True, "data_quality_required": "high"},
        "manufacturing": {"typical_margin": 0.18, "license_critical": False, "data_quality_required": "medium"},
    }

    def judge_deal(self, deal: Deal, evidence: List[Evidence], thesis: Thesis) -> Dict:
        stage = (deal.stage or "").lower().strip()
        geography = (deal.geography or "").lower().replace(" ", "_")
        sector = (deal.sector or "").lower().strip()

        dimension_scores = {
            "financial": self._score_financial(evidence, deal, thesis),
            "governance": self._score_governance(evidence, deal, thesis),
            "market": self._score_market(evidence, deal),
            "team": self._score_team(evidence, deal),
            "product": self._score_product(evidence, deal, stage),
            "data_confidence": self._score_data_confidence(evidence, deal),
        }

        kill = self._detect_kill_signals(evidence, thesis, dimension_scores, deal)
        readiness = self.calculate_readiness(dimension_scores, thesis)
        alignment = self.calculate_alignment(dimension_scores, thesis)
        confidence_num = dimension_scores.get("data_confidence", 0)
        confidence_level = self.calculate_confidence(confidence_num)
        explanations = self.generate_explanations(deal, evidence, dimension_scores, kill)
        missing = self.suggest_missing_evidence(deal, evidence)

        return {
            "investment_readiness": readiness,
            "thesis_alignment": alignment,
            "confidence_level": confidence_level,
            "kill_signals": kill,
            "dimension_scores": dimension_scores,
            "explanations": explanations,
            "suggested_missing": missing,
        }

    def _score_financial(self, evidence: List[Evidence], deal: Deal, thesis: Thesis) -> float:
        base_score = 30.0
        stage = (deal.stage or "").lower().strip() or "early_revenue"

        if self._check_financial_requirements(evidence, stage):
            base_score += 20

        if self._has_revenue_data(evidence):
            base_score += 15

        margin = self._extract_gross_margin(evidence)
        if margin is not None:
            sector_norm = self.SECTOR_NORMS.get((deal.sector or "").lower().strip(), {}).get("typical_margin", 0.25)
            if margin >= sector_norm * 0.8:
                base_score += 20
            elif margin > 0:
                base_score += 10

        if self._has_audited_financials(evidence):
            base_score += 15
        elif stage == "mature":
            base_score -= 20

        return max(0.0, min(base_score, 100.0))

    def _score_governance(self, evidence: List[Evidence], deal: Deal, thesis: Thesis) -> float:
        base_score = 40.0
        stage = (deal.stage or "").lower().strip() or "early_revenue"

        informality_level = self._assess_informality(evidence)
        tolerance = self.INFORMALITY_TOLERANCE.get(stage, self.INFORMALITY_TOLERANCE["early_revenue"])
        if informality_level <= tolerance["max_acceptable"]:
            base_score += 20 * float(tolerance["penalty_reduction"])

        has_family_ownership = self._check_family_ownership(evidence)
        has_governance_conflict = self._check_governance_conflicts(evidence)
        if has_family_ownership and not has_governance_conflict:
            base_score += 10
        elif has_governance_conflict:
            base_score -= 20

        if self._check_formalization_efforts(evidence):
            base_score += 15

        if self._has_shareholder_agreement(evidence):
            base_score += 10
        if self._has_board_structure(evidence):
            base_score += 10

        return max(0.0, min(base_score, 100.0))

    def _score_market(self, evidence: List[Evidence], deal: Deal) -> float:
        base_score = 50.0
        geo = (deal.geography or "").lower().replace(" ", "_")
        geo_risks = self.GEOGRAPHY_RISK_FACTORS.get(geo, {"fx_risk": 0.2, "infrastructure_risk": 0.2})
        total_risk = float(sum(geo_risks.values()))

        if total_risk > 0.5:
            if self._has_risk_mitigation(evidence, geo_risks):
                base_score += 10
            else:
                base_score -= 15

        concentration = self._calculate_customer_concentration(evidence)
        if concentration is not None:
            if concentration > 0.7:
                base_score -= 20
            elif concentration > 0.5:
                if self._has_anchor_customer_quality(evidence):
                    base_score -= 5
                else:
                    base_score -= 15

        if self._has_market_analysis(evidence):
            base_score += 15
        if self._has_customer_contracts(evidence):
            base_score += 15

        return max(0.0, min(base_score, 100.0))

    def _score_team(self, evidence: List[Evidence], deal: Deal) -> float:
        base_score = 50.0

        if self._survived_crisis(evidence):
            base_score += 15

        if self._has_local_market_expertise(evidence, (deal.geography or "").lower()):
            base_score += 10

        if self._has_diaspora_background(evidence):
            base_score += 10

        if self._has_team_bios(evidence):
            base_score += 10
        if self._has_org_chart(evidence):
            base_score += 5

        return max(0.0, min(base_score, 100.0))

    def _score_product(self, evidence: List[Evidence], deal: Deal, stage: str) -> float:
        base_score = 50.0
        has_pmf = any(
            (e.evidence_type == "market" and (e.extracted_data or {}).get("pmf") is True)
            or ((e.extracted_data or {}).get("retention_rate", 0) >= 0.6)
            for e in evidence
        )
        if has_pmf:
            base_score += 15

        traction = 0
        for e in evidence:
            data = e.extracted_data or {}
            if "active_users" in data and isinstance(data["active_users"], (int, float)):
                traction += 1
            if "mrr" in data and isinstance(data["mrr"], (int, float)):
                traction += 1
        if traction >= 2:
            base_score += 15
        elif traction == 1:
            base_score += 8

        has_product_docs = any(e.evidence_type in ("product", "operations") for e in evidence)
        if has_product_docs:
            base_score += 10

        return max(0.0, min(base_score, 100.0))

    def _score_data_confidence(self, evidence: List[Evidence], deal: Deal) -> float:
        evidence_types = set(e.evidence_type for e in evidence)
        completeness = min(len(evidence_types) / 5.0, 1.0)
        consistency_score = self._check_data_consistency(evidence)
        confidence = (completeness * 0.4) + (consistency_score * 0.6)
        if (deal.stage or "").lower() in ["pre_revenue", "early_revenue"]:
            confidence = min(confidence + 0.15, 1.0)
        return max(0.0, min(confidence * 100.0, 100.0))

    def _detect_kill_signals(self, evidence: List[Evidence], thesis: Thesis, dimension_scores: Dict, deal: Deal) -> Dict:
        if self._detect_fraud_patterns(evidence):
            return {"type": "HARD_KILL", "reason": "fraud_indicators", "detail": "Inconsistent financial records across documents"}

        if (deal.stage or "").lower() == "mature" and dimension_scores.get("financial", 0) < 30:
            return {"type": "HARD_KILL", "reason": "financial_insolvency", "detail": "Negative cash flow with no path to recovery"}

        thesis_kills = (thesis.kill_conditions or []) if isinstance(thesis.kill_conditions, list) else []
        if "no_audited_financials" in thesis_kills:
            if (deal.stage or "").lower() == "mature" and not self._has_audited_financials(evidence):
                return {"type": "HARD_KILL", "reason": "no_audited_financials", "detail": "Required by fund thesis"}

        if self._has_fx_death_spiral(evidence, deal):
            return {"type": "HARD_KILL", "reason": "fx_structural_risk", "detail": "Revenue in local currency, debt in hard currency, no hedge"}

        concentration = self._calculate_customer_concentration(evidence)
        if concentration is not None and concentration > 0.7 and dimension_scores.get("governance", 0) < 40:
            return {"type": "HARD_KILL", "reason": "concentration_plus_weak_governance", "detail": "Over-reliance on one customer + poor governance = high failure risk"}

        if dimension_scores.get("financial", 0) < 40:
            return {"type": "POTENTIAL_KILL", "reason": "weak_financial_health", "detail": "Financial dimension below threshold"}

        if dimension_scores.get("governance", 0) < 30 and (deal.stage or "").lower() in ["growth", "mature"]:
            return {"type": "POTENTIAL_KILL", "reason": "governance_failure", "detail": "Governance too weak for stage"}

        return {"type": "NONE"}

    def calculate_readiness(self, dimension_scores: Dict[str, float], thesis: Thesis) -> float:
        weights = self.default_weights()
        total = 0.0
        for k, w in weights.items():
            total += (dimension_scores.get(k, 0.0) / 100.0) * float(w)
        return max(0.0, min(total * 100.0, 100.0))

    def calculate_alignment(self, dimension_scores: Dict[str, float], thesis: Thesis) -> float:
        weights = thesis.weights if isinstance(thesis.weights, dict) else self.default_weights()
        s = sum(float(v) for v in weights.values()) or 1.0
        weights = {k: float(v) / s for k, v in weights.items()}
        total = 0.0
        for k, w in weights.items():
            total += (dimension_scores.get(k, 0.0) / 100.0) * w
        return max(0.0, min(total * 100.0, 100.0))

    def calculate_confidence(self, confidence_score: float) -> str:
        if confidence_score >= 75:
            return "high"
        if confidence_score >= 50:
            return "medium"
        return "low"

    def generate_explanations(self, deal: Deal, evidence: List[Evidence], dimension_scores: Dict, kill: Dict) -> List[str]:
        notes: List[str] = []
        if self._has_audited_financials(evidence):
            notes.append("Audited or management accounts present")
        if self._has_revenue_data(evidence):
            notes.append("Revenue data present across financial documents")
        if self._has_risk_mitigation(evidence, self.GEOGRAPHY_RISK_FACTORS.get((deal.geography or "").lower(), {})):
            notes.append("Mitigations in place for geography risks")
        if self._survived_crisis(evidence):
            notes.append("Demonstrated resilience through crisis")
        if kill.get("type") != "NONE":
            notes.append(f"Kill signal: {kill.get('reason')}")
        return notes

    def suggest_missing_evidence(self, deal: Deal, evidence: List[Evidence]) -> List[str]:
        stage = (deal.stage or "").lower().strip() or "early_revenue"
        required = list(self.STAGE_FINANCIAL_REQUIREMENTS.get(stage, []))
        available = set()
        for e in evidence:
            data = e.extracted_data or {}
            subtype = data.get("subtype")
            if subtype:
                available.add(subtype)
            if e.evidence_type == "financial":
                available.add("bank_statements")
        missing = [r for r in required if r not in available]
        return missing

    def default_weights(self) -> Dict[str, float]:
        return {
            "financial": 0.30,
            "governance": 0.20,
            "market": 0.20,
            "team": 0.15,
            "product": 0.10,
            "data_confidence": 0.05,
        }

    def _check_financial_requirements(self, evidence: List[Evidence], stage: str) -> bool:
        required = self.STAGE_FINANCIAL_REQUIREMENTS.get(stage, [])
        if "audited_financials_required" in required:
            return self._has_audited_financials(evidence)
        if "audited_financials_or_management_accounts" in required:
            return self._has_audited_financials(evidence) or self._has_management_accounts(evidence)
        return any(e.evidence_type == "financial" for e in evidence)

    def _assess_informality(self, evidence: List[Evidence]) -> float:
        informality_score = 50.0
        if self._has_audited_financials(evidence):
            informality_score -= 30
        if self._has_business_registration(evidence):
            informality_score -= 20
        if self._has_tax_compliance(evidence):
            informality_score -= 20
        return max(informality_score, 0.0)

    def _check_formalization_efforts(self, evidence: List[Evidence]) -> bool:
        recent = {"business_registration", "accountant_hired", "license_application", "tax_registration"}
        for e in evidence:
            data = e.extracted_data or {}
            subtype = data.get("subtype")
            if subtype in recent:
                return True
        return False

    def _survived_crisis(self, evidence: List[Evidence]) -> bool:
        crisis_indicators = {"covid_survival", "fx_crisis_survival", "customer_loss_survival"}
        for e in evidence:
            data = e.extracted_data or {}
            if data.get("crisis_survival") in crisis_indicators:
                return True
        return False

    def _has_fx_death_spiral(self, evidence: List[Evidence], deal: Deal) -> bool:
        has_local_revenue = any((e.extracted_data or {}).get("revenue_currency") in {"NGN", "KES", "ZAR", "GHS"} for e in evidence)
        has_hard_currency_debt = any((e.extracted_data or {}).get("debt_currency") in {"USD", "EUR", "GBP"} for e in evidence)
        has_hedge = any((e.extracted_data or {}).get("fx_hedge") is True for e in evidence)
        return bool(has_local_revenue and has_hard_currency_debt and not has_hedge)

    def _calculate_customer_concentration(self, evidence: List[Evidence]) -> Optional[float]:
        for e in evidence:
            data = e.extracted_data or {}
            if "customer_concentration" in data and isinstance(data["customer_concentration"], (int, float)):
                return float(data["customer_concentration"])
        return None

    def _has_anchor_customer_quality(self, evidence: List[Evidence]) -> bool:
        indicators = {"multinational_customer", "tier1_corporate", "government_with_escrow"}
        for e in evidence:
            data = e.extracted_data or {}
            if data.get("customer_type") in indicators:
                return True
        return False

    def _check_data_consistency(self, evidence: List[Evidence]) -> float:
        revenues: List[float] = []
        for e in evidence:
            if e.evidence_type == "financial":
                data = e.extracted_data or {}
                if isinstance(data.get("revenue"), (int, float)):
                    revenues.append(float(data["revenue"]))
        if len(revenues) < 2:
            return 0.7
        avg = sum(revenues) / len(revenues)
        if avg == 0:
            return 0.4
        variance = sum((r - avg) ** 2 for r in revenues) / len(revenues)
        ratio = variance / abs(avg)
        if ratio < 0.1:
            return 1.0
        if ratio < 0.3:
            return 0.7
        return 0.4

    def _detect_fraud_patterns(self, evidence: List[Evidence]) -> bool:
        fraud_signals = 0
        if self._check_data_consistency(evidence) < 0.4:
            fraud_signals += 1
        missing_tax = not self._has_tax_compliance(evidence)
        if missing_tax:
            fraud_signals += 1
        return fraud_signals >= 2

    def _has_audited_financials(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if data.get("subtype") == "audited_financials" or data.get("audited_financials") is True:
                return True
        return False

    def _has_management_accounts(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if data.get("subtype") == "management_accounts" or data.get("management_accounts") is True:
                return True
        return False

    def _has_revenue_data(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            if e.evidence_type == "financial":
                data = e.extracted_data or {}
                if any(k in data for k in ("revenue", "sales", "turnover")):
                    return True
        return False

    def _extract_gross_margin(self, evidence: List[Evidence]) -> Optional[float]:
        for e in evidence:
            if e.evidence_type == "financial":
                data = e.extracted_data or {}
                if isinstance(data.get("gross_margin"), (int, float)):
                    gm = float(data["gross_margin"])  # already 0-1 or 0-100?
                    if gm > 1.0:
                        gm = gm / 100.0
                    return max(0.0, min(gm, 1.0))
        return None

    def _has_shareholder_agreement(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if e.evidence_type == "governance" and (data.get("shareholder_agreement") is True or data.get("subtype") == "shareholder_agreement"):
                return True
        return False

    def _has_board_structure(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if e.evidence_type == "governance" and (data.get("board_structure") is True or data.get("subtype") == "board_structure"):
                return True
        return False

    def _has_business_registration(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if (data.get("business_registration") is True) or data.get("subtype") == "business_registration":
                return True
        return False

    def _has_tax_compliance(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if (data.get("tax_compliance") is True) or data.get("subtype") == "tax_clearance":
                return True
        return False

    def _has_risk_mitigation(self, evidence: List[Evidence], geo_risks: Dict) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if data.get("fx_hedge") is True:
                return True
            if data.get("generator") is True:
                return True
            if data.get("redundant_connectivity") is True:
                return True
            if data.get("regulatory_license") is True:
                return True
        return False

    def _has_market_analysis(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            if e.evidence_type == "market":
                data = e.extracted_data or {}
                if data.get("market_analysis") is True or data.get("subtype") == "market_report":
                    return True
        return False

    def _has_customer_contracts(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            if e.evidence_type in ("market", "operations"):
                data = e.extracted_data or {}
                if data.get("customer_contracts") is True or isinstance(data.get("contracts"), list):
                    return True
        return False

    def _has_local_market_expertise(self, evidence: List[Evidence], geography: str) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if data.get("local_expertise") is True or geography and data.get("country_experience") == geography:
                return True
        return False

    def _has_diaspora_background(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            data = e.extracted_data or {}
            if data.get("diaspora_background") is True:
                return True
        return False

    def _check_family_ownership(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            if e.evidence_type == "governance":
                data = e.extracted_data or {}
                if data.get("family_owned") is True:
                    return True
        return False

    def _check_governance_conflicts(self, evidence: List[Evidence]) -> bool:
        for e in evidence:
            if e.evidence_type == "governance":
                data = e.extracted_data or {}
                if data.get("conflict_of_interest") is True or data.get("related_party_transactions_unmanaged") is True:
                    return True
        return False
