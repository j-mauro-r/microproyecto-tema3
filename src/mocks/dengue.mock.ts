import type { CityForecast, DashboardData, SeriesPoint } from "@/types/dengue";

const MONTHS = (() => {
  const out: string[] = [];
  for (let y = 2022; y <= 2026; y++) {
    for (let m = 1; m <= 12; m++) {
      if (y === 2026 && m > 9) break;
      out.push(`${y}-${String(m).padStart(2, "0")}`);
    }
  }
  return out;
})();

const LAST_OBSERVED = "2026-07";

function buildSeries(opts: {
  base: number;
  amplitude: number;
  outbreakYears: Record<number, number>;
  trendEnd: number;
  seed: number;
}): SeriesPoint[] {
  const { base, amplitude, outbreakYears, trendEnd, seed } = opts;
  let rnd = seed;
  const random = () => {
    rnd = (rnd * 9301 + 49297) % 233280;
    return rnd / 233280;
  };

  return MONTHS.map((month, i) => {
    const [yStr, mStr] = month.split("-");
    const year = Number(yStr);
    const m = Number(mStr);
    const seasonal = Math.sin(((m - 3) / 12) * Math.PI * 2);
    const p50 = Math.round(base + amplitude * seasonal);
    const p25 = Math.round(p50 * 0.68);
    const p75 = Math.round(p50 * 1.42);

    const outbreak = outbreakYears[year] ?? 1;
    const drift = 1 + (i / MONTHS.length) * trendEnd;
    const noise = 0.88 + random() * 0.28;
    const raw = p50 * outbreak * drift * noise;

    const isForecast = month > LAST_OBSERVED;
    const observed = isForecast ? null : Math.max(10, Math.round(raw));

    return {
      month,
      observed,
      p25,
      p50,
      p75,
      isExcess: observed !== null && observed > p75,
      isForecast,
    };
  });
}

const bucaramanga: CityForecast = {
  city: { id: "bucaramanga", name: "Bucaramanga" },
  predictions: {
    "T+1": {
      horizon: "T+1",
      targetMonth: "2026-08",
      label: 1,
      probability: 0.62,
      confidenceInterval: [0.48, 0.75],
    },
    "T+2": {
      horizon: "T+2",
      targetMonth: "2026-09",
      label: 1,
      probability: 0.78,
      confidenceInterval: [0.61, 0.89],
    },
  },
  endemicChannel: {
    ratioToP75: 0.92,
    referenceMonth: "2026-07",
    observedCases: 168,
    p75: 183,
    description: "Cercano al P75",
  },
  series: buildSeries({
    base: 95,
    amplitude: 38,
    outbreakYears: { 2022: 1, 2023: 1.05, 2024: 1.45, 2025: 1.0, 2026: 1.5 },
    trendEnd: 0.35,
    seed: 17,
  }),
  featureImportances: [
    { feature: "Rezago t−1 (casos)", importance: 0.32, group: "lag" },
    { feature: "Rezago t−2 (casos)", importance: 0.21, group: "lag" },
    { feature: "Promedio móvil (3m)", importance: 0.16, group: "lag" },
    { feature: "Precipitación (mm)", importance: 0.12, group: "climate" },
    { feature: "Temperatura media (°C)", importance: 0.08, group: "climate" },
    { feature: "Estacionalidad", importance: 0.06, group: "seasonality" },
  ],
  insights: [
    {
      id: "bga-1",
      level: "high",
      title: "Riesgo alto sostenido",
      detail: "La probabilidad de exceso a T+2 es 78%, por encima del umbral de decisión (50%).",
    },
    {
      id: "bga-2",
      level: "medium",
      title: "Impulsores recientes",
      detail:
        "Los rezagos t−1 y t−2 junto con precipitación por encima de lo normal concentran el 65% de la importancia del modelo.",
    },
    {
      id: "bga-3",
      level: "low",
      title: "Canal endémico",
      detail: "Los casos de julio 2026 alcanzan el 92% del P75; el umbral podría superarse en semanas.",
    },
  ],
  recommendation:
    "Reforzar vigilancia, preparación asistencial y control vectorial en Bucaramanga para los próximos 2 meses.",
};

const cali: CityForecast = {
  city: { id: "cali", name: "Cali" },
  predictions: {
    "T+1": {
      horizon: "T+1",
      targetMonth: "2026-08",
      label: 0,
      probability: 0.34,
      confidenceInterval: [0.22, 0.47],
    },
    "T+2": {
      horizon: "T+2",
      targetMonth: "2026-09",
      label: 0,
      probability: 0.46,
      confidenceInterval: [0.33, 0.6],
    },
  },
  endemicChannel: {
    ratioToP75: 0.71,
    referenceMonth: "2026-07",
    observedCases: 121,
    p75: 170,
    description: "Bajo P75",
  },
  series: buildSeries({
    base: 88,
    amplitude: 30,
    outbreakYears: { 2022: 1, 2023: 1.3, 2024: 1.2, 2025: 0.95, 2026: 1.12 },
    trendEnd: 0.15,
    seed: 41,
  }),
  featureImportances: [
    { feature: "Rezago t−1 (casos)", importance: 0.24, group: "lag" },
    { feature: "Promedio móvil (3m)", importance: 0.19, group: "lag" },
    { feature: "Precipitación (mm)", importance: 0.17, group: "climate" },
    { feature: "Rezago t−2 (casos)", importance: 0.13, group: "lag" },
    { feature: "Temperatura media (°C)", importance: 0.09, group: "climate" },
    { feature: "Estacionalidad", importance: 0.07, group: "seasonality" },
  ],
  insights: [
    {
      id: "cali-1",
      level: "medium",
      title: "Riesgo moderado y creciente",
      detail: "La probabilidad pasa de 34% (T+1) a 46% (T+2), acercándose al umbral de exceso.",
    },
    {
      id: "cali-2",
      level: "low",
      title: "Bajo el canal endémico",
      detail: "Los casos observados están al 71% del P75, sin señal de exceso en curso.",
    },
    {
      id: "cali-3",
      level: "low",
      title: "Impulsores climáticos",
      detail: "Precipitación y promedio móvil explican la tendencia al alza más que los rezagos inmediatos.",
    },
  ],
  recommendation:
    "Mantener vigilancia rutinaria en Cali y revisar el pronóstico el próximo corte mensual.",
};

export const dashboardMock: DashboardData = {
  updatedAt: "2026-08-01T08:00:00-05:00",
  cities: [bucaramanga.city, cali.city],
  forecasts: { bucaramanga, cali },
};
