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
}

export interface LatestResponseDto {
  schema_version: string;
  request_id: string;
  prediction_snapshot: {
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
    };
    predictions: PredictionDto[];
  };
}

export interface MonthlyRunResponseDto {
  schema_version: string;
  request_id: string;
  run: { run_id: string; status: string; reference_month: string };
}
