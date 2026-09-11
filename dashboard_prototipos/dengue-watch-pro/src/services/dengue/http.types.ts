export interface ErrorEnvelopeDto {
  error: { code: string; message: string; request_id?: string; details?: unknown };
}

export interface PredictionDto {
  divipola: string;
  municipality: string;
  horizon: string;
  target_month: string;
  output_type: string;
  probability: number | null;
  expected_cases: number | null;
  risk_score: number | null;
  label: string | null;
  decision_threshold: number | null;
  decision_rule?: {
    type: string | null;
    probability_threshold: number | null;
    target_month_p75: number | null;
    decision_threshold_cases: number | null;
    version: string | null;
  } | null;
  explanation?: {
    available: boolean;
    method: string | null;
    scope: string | null;
    top_features: Array<{
      feature: string;
      value: number | string | null;
      contribution: number;
      group: string | null;
    }>;
  };
}

export interface SnapshotDto {
  run_id: string;
  generated_at: string;
  reference_month: string;
  source_file_sha256: string;
  champion: {
    name: string;
    version: string;
    output_type: string;
    supported_horizons: string[];
    feature_contract_version: string;
    feature_contract_sha256: string;
    mlflow_run_id?: string | null;
    artifact_sha256?: string | null;
    decision_rule_version?: string | null;
    explanation_method?: string | null;
  };
  predictions: PredictionDto[];
  data_quality?: {
    status: string;
    last_observed_month: string;
    epidemiological_completeness: number | null;
    climate_completeness: number | null;
    warnings: string[];
  } | null;
  current_status?: Record<
    string,
    {
      reference_month: string;
      observed_cases: number | null;
      p25: number | null;
      p50: number | null;
      p75: number | null;
      ratio_to_p75: number | null;
      endemic_zone: string | null;
    }
  >;
}

export interface LatestResponseDto {
  schema_version: string;
  request_id: string;
  prediction_snapshot: SnapshotDto;
}

export interface HistoryResponseDto {
  items: Array<SnapshotDto & { completed_at: string }>;
}

export interface MonthlyRunResponseDto {
  schema_version: string;
  request_id: string;
  run: { run_id: string; status: string; reference_month: string };
}
