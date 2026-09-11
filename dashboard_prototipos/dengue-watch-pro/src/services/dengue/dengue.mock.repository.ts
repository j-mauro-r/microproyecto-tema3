import type { DengueRepository } from "./dengue.repository";
import type { MonthlyRunReceipt, PredictionHistoryItem, PredictionSnapshot } from "@/types/dengue";

/** Explicit test fake. Production composition never imports this class. */
export class MockDengueRepository implements DengueRepository {
  constructor(private readonly snapshot: PredictionSnapshot) {}
  getLatest(): Promise<PredictionSnapshot> {
    return Promise.resolve(this.snapshot);
  }
  getHistory(): Promise<PredictionHistoryItem[]> {
    return Promise.resolve([]);
  }
  createMonthlyRun(): Promise<MonthlyRunReceipt> {
    return Promise.reject(new Error("Upload is unavailable in the explicit mock."));
  }
}
