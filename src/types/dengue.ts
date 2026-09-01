export type CityId = "bucaramanga" | "cali";

export type Horizon = "T+1" | "T+2";

/** Salida binaria del modelo: 0 = NO EXCESO, 1 = EXCESO */
export type ExcessClass = 0 | 1;

export interface City {
  id: CityId;
  name: string;
}

export interface Prediction {
  horizon: Horizon;
  /** Mes objetivo del pronóstico, formato YYYY-MM */
  targetMonth: string;
  label: ExcessClass;
  probability: number; // 0..1
  confidenceInterval?: [number, number];
}

export interface EndemicChannelStatus {
  /** Porcentaje de los casos observados respecto al P75 del canal endémico */
  ratioToP75: number; // 1 = igual al P75
  referenceMonth: string;
  observedCases: number;
  p75: number;
  description: string;
}

export interface SeriesPoint {
  month: string; // YYYY-MM
  observed: number | null;
  p25: number;
  p50: number;
  p75: number;
  isExcess: boolean;
  isForecast: boolean;
}

export interface FeatureImportance {
  feature: string;
  importance: number; // SHAP promedio absoluto
  group: "lag" | "climate" | "seasonality";
}

export interface Insight {
  id: string;
  level: "high" | "medium" | "low";
  title: string;
  detail: string;
}

export interface CityForecast {
  city: City;
  predictions: Record<Horizon, Prediction>;
  endemicChannel: EndemicChannelStatus;
  series: SeriesPoint[];
  featureImportances: FeatureImportance[];
  insights: Insight[];
  recommendation: string;
}

export interface DashboardData {
  updatedAt: string;
  cities: City[];
  forecasts: Record<CityId, CityForecast>;
}
