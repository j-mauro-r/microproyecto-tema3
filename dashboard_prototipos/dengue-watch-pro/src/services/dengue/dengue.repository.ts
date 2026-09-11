import type { MonthlyRunReceipt, PredictionHistoryItem, PredictionSnapshot } from "@/types/dengue";

export interface DengueRepository {
  getLatest(signal?: AbortSignal): Promise<PredictionSnapshot>;
  getHistory(signal?: AbortSignal): Promise<PredictionHistoryItem[]>;
  createMonthlyRun(file: File, referenceMonth: string): Promise<MonthlyRunReceipt>;
}
