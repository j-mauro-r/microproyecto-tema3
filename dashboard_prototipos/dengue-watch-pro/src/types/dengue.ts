export type CityId = "bucaramanga" | "cali";
export type MunicipalityCode = "68001" | "76001";
export type Horizon = "T+1" | "T+2";

export interface Prediction {
  divipola: MunicipalityCode;
  municipality: string;
  horizon: Horizon;
  targetMonth: string;
  outputType: string;
  probability: number | null;
  expectedCases: number | null;
  riskScore: number | null;
  label: string | null;
  decisionThreshold: number | null;
}

export interface ChampionMetadata {
  name: string;
  version: string;
  outputType: string;
  supportedHorizons: Horizon[];
  featureContractVersion: string;
  featureContractSha256: string;
}

export interface PredictionSnapshot {
  runId: string;
  generatedAt: string;
  referenceMonth: string;
  sourceFileSha256: string;
  champion: ChampionMetadata;
  predictions: Prediction[];
}

export interface MonthlyRunReceipt {
  runId: string;
  referenceMonth: string;
  status: "COMPLETED";
}
