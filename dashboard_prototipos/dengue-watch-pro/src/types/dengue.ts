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
  decisionRule?: DecisionRule | null;
  explanation?: LocalExplanation;
}

export interface DecisionRule {
  type: string | null;
  probabilityThreshold: number | null;
  targetMonthP75: number | null;
  decisionThresholdCases: number | null;
  version: string | null;
}

export interface ExplanationFeature {
  feature: string;
  value: number | string | null;
  contribution: number;
  group: string | null;
}

export interface LocalExplanation {
  available: boolean;
  method: string | null;
  scope: string | null;
  topFeatures: ExplanationFeature[];
}

export interface DataQuality {
  status: string;
  lastObservedMonth: string;
  epidemiologicalCompleteness: number | null;
  climateCompleteness: number | null;
  warnings: string[];
}

export interface CurrentStatus {
  referenceMonth: string;
  observedCases: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  ratioToP75: number | null;
  endemicZone: string | null;
}

export interface ChampionMetadata {
  name: string;
  version: string;
  outputType: string;
  supportedHorizons: Horizon[];
  featureContractVersion: string;
  featureContractSha256: string;
  mlflowRunId?: string | null;
  artifactSha256?: string | null;
  decisionRuleVersion?: string | null;
  explanationMethod?: string | null;
}

export interface PredictionSnapshot {
  runId: string;
  generatedAt: string;
  referenceMonth: string;
  sourceFileSha256: string;
  champion: ChampionMetadata;
  predictions: Prediction[];
  dataQuality?: DataQuality | null;
  currentStatus?: Partial<Record<MunicipalityCode, CurrentStatus>>;
}

export interface PredictionHistoryItem extends PredictionSnapshot {
  completedAt: string;
}

export interface MonthlyRunReceipt {
  runId: string;
  referenceMonth: string;
  status: "COMPLETED";
}
