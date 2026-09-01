import { dashboardMock } from "@/mocks/dengue.mock";
import type { CityForecast, CityId, DashboardData } from "@/types/dengue";
import type { DengueRepository } from "./dengue.repository";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export class MockDengueRepository implements DengueRepository {
  async getDashboard(): Promise<DashboardData> {
    await delay(120);
    return dashboardMock;
  }

  async getCityForecast(cityId: CityId): Promise<CityForecast> {
    await delay(80);
    return dashboardMock.forecasts[cityId];
  }
}
