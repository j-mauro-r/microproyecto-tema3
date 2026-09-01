import type { CityForecast, CityId, DashboardData } from "@/types/dengue";

/**
 * Contrato de acceso a datos del modelo de alerta temprana.
 * Sustituible por una implementación HTTP sin tocar la capa de UI.
 */
export interface DengueRepository {
  getDashboard(): Promise<DashboardData>;
  getCityForecast(cityId: CityId): Promise<CityForecast>;
}
