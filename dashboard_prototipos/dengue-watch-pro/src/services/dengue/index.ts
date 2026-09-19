import { getApiBaseUrl } from "./api-config";
import { HttpDengueRepository } from "./dengue.http.repository";

export const dengueRepository = new HttpDengueRepository(getApiBaseUrl);

export { BiomacApiError, HttpDengueRepository } from "./dengue.http.repository";
export { BiomacConfigurationError, normalizeApiBaseUrl } from "./api-config";
export type { DengueRepository } from "./dengue.repository";
