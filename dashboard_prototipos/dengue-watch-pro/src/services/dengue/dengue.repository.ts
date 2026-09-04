import type { MonthlyRunReceipt, PredictionSnapshot } from "@/types/dengue";

export interface DengueRepository {
  getLatest(signal?: AbortSignal): Promise<PredictionSnapshot>;
  createMonthlyRun(file: File, referenceMonth: string): Promise<MonthlyRunReceipt>;
}
