// ... (keep the existing imports) ...

interface Judgment {
  investment_readiness: string;
  thesis_alignment: string;
  kill_signals: { type: string; reason?: string; detail?: string };
  confidence_level: string;
  dimension_scores: {
    financial: number;
    governance: number;
    market: number;
    team: number;
    product: number;
    data_confidence: number;
  };
  explanations: {
    investment_readiness: string;
    thesis_alignment: string;
    kill_signals: string;
    confidence_level: string;
  };
  missing_evidence?: Array<{
    type: string;
    action: string;
    impact: string;
  }>;
  created_at: string;
  id: string;
  deal_id: string;
}

// ... (rest of the file remains the same) ...
