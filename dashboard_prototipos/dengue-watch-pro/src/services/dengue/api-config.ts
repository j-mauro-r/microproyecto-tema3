export class BiomacConfigurationError extends Error {
  constructor() {
    super("BIOMAC API no está configurada correctamente.");
    this.name = "BiomacConfigurationError";
  }
}

export function normalizeApiBaseUrl(raw: string | undefined): string {
  const value = raw?.trim().replace(/\/+$/, "");
  if (!value) throw new BiomacConfigurationError();
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new BiomacConfigurationError();
  }
  if (!["http:", "https:"].includes(url.protocol) || url.pathname !== "/api/v2") {
    throw new BiomacConfigurationError();
  }
  return url.toString().replace(/\/$/, "");
}

export function getApiBaseUrl(): string {
  return normalizeApiBaseUrl(import.meta.env["VITE_BIOMAC_API_BASE_URL"]);
}
