import type {
  Horizon,
  MonthlyRunReceipt,
  MunicipalityCode,
  PredictionHistoryItem,
  PredictionSnapshot,
} from "@/types/dengue";
import type { DengueRepository } from "./dengue.repository";
import type {
  ErrorEnvelopeDto,
  HistoryResponseDto,
  LatestResponseDto,
  MonthlyRunResponseDto,
  SnapshotDto,
} from "./http.types";

export class BiomacApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly requestId?: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "BiomacApiError";
  }
}

export class HttpDengueRepository implements DengueRepository {
  constructor(
    private readonly baseUrl: string | (() => string),
    private readonly transport: typeof fetch = (...args) => fetch(...args),
  ) {}

  async getLatest(signal?: AbortSignal): Promise<PredictionSnapshot> {
    const response = await this.request(
      `${this.resolveBaseUrl()}/predictions/latest`,
      signal ? { signal } : undefined,
    );
    const body = (await this.json(response)) as Partial<LatestResponseDto>;
    const value = body.prediction_snapshot;
    if (!value?.run_id || !Array.isArray(value.predictions) || !value.champion) {
      throw this.invalidPayload(response.status);
    }
    return this.mapSnapshot(value);
  }

  async getHistory(signal?: AbortSignal): Promise<PredictionHistoryItem[]> {
    const response = await this.request(
      `${this.resolveBaseUrl()}/predictions/history?limit=12`,
      signal ? { signal } : undefined,
    );
    const body = (await this.json(response)) as Partial<HistoryResponseDto>;
    if (!Array.isArray(body.items)) throw this.invalidPayload(response.status);
    return body.items.map((item) => ({
      ...this.mapSnapshot(item),
      completedAt: item.completed_at,
    }));
  }

  private mapSnapshot(value: SnapshotDto): PredictionSnapshot {
    const predictions = value.predictions.map((item) => {
      if (!(["68001", "76001"] as string[]).includes(item.divipola)) {
        throw this.invalidPayload(200);
      }
      if (!(["T+1", "T+2"] as string[]).includes(item.horizon)) {
        throw this.invalidPayload(200);
      }
      return {
        divipola: item.divipola as MunicipalityCode,
        municipality: item.municipality,
        horizon: item.horizon as Horizon,
        targetMonth: item.target_month,
        outputType: item.output_type,
        probability: item.probability,
        expectedCases: item.expected_cases,
        riskScore: item.risk_score,
        label: item.label,
        decisionThreshold: item.decision_threshold,
        decisionRule: item.decision_rule
          ? {
              type: item.decision_rule.type,
              probabilityThreshold: item.decision_rule.probability_threshold,
              targetMonthP75: item.decision_rule.target_month_p75,
              decisionThresholdCases: item.decision_rule.decision_threshold_cases,
              version: item.decision_rule.version,
            }
          : null,
        explanation: item.explanation
          ? {
              available: item.explanation.available,
              method: item.explanation.method,
              scope: item.explanation.scope,
              topFeatures: item.explanation.top_features.map((feature) => ({
                feature: feature.feature,
                value: feature.value,
                contribution: feature.contribution,
                group: feature.group,
              })),
            }
          : { available: false, method: null, scope: null, topFeatures: [] },
      };
    });
    return {
      runId: value.run_id,
      generatedAt: value.generated_at,
      referenceMonth: value.reference_month,
      sourceFileSha256: value.source_file_sha256,
      champion: {
        name: value.champion.name,
        version: value.champion.version,
        outputType: value.champion.output_type,
        supportedHorizons: value.champion.supported_horizons as Horizon[],
        featureContractVersion: value.champion.feature_contract_version,
        featureContractSha256: value.champion.feature_contract_sha256,
        mlflowRunId: value.champion.mlflow_run_id ?? null,
        artifactSha256: value.champion.artifact_sha256 ?? null,
        decisionRuleVersion: value.champion.decision_rule_version ?? null,
        explanationMethod: value.champion.explanation_method ?? null,
      },
      predictions,
      dataQuality: value.data_quality
        ? {
            status: value.data_quality.status,
            lastObservedMonth: value.data_quality.last_observed_month,
            epidemiologicalCompleteness: value.data_quality.epidemiological_completeness,
            climateCompleteness: value.data_quality.climate_completeness,
            warnings: value.data_quality.warnings,
          }
        : null,
      currentStatus: Object.fromEntries(
        Object.entries(value.current_status ?? {}).map(([code, status]) => [
          code,
          {
            referenceMonth: status.reference_month,
            observedCases: status.observed_cases,
            p25: status.p25,
            p50: status.p50,
            p75: status.p75,
            ratioToP75: status.ratio_to_p75,
            endemicZone: status.endemic_zone,
          },
        ]),
      ),
    };
  }

  async createMonthlyRun(file: File, referenceMonth: string): Promise<MonthlyRunReceipt> {
    const form = new FormData();
    form.append("file", file);
    form.append("reference_month", referenceMonth);
    const response = await this.request(`${this.resolveBaseUrl()}/monthly-runs`, {
      method: "POST",
      body: form,
    });
    const body = (await this.json(response)) as Partial<MonthlyRunResponseDto>;
    if (!body.run?.run_id || body.run.status !== "COMPLETED" || !body.run.reference_month) {
      throw this.invalidPayload(response.status);
    }
    return {
      runId: body.run.run_id,
      referenceMonth: body.run.reference_month,
      status: "COMPLETED",
    };
  }

  private async request(url: string, init?: RequestInit): Promise<Response> {
    let response: Response;
    try {
      response = await this.transport(url, { ...init, headers: { Accept: "application/json" } });
    } catch {
      throw new BiomacApiError("No fue posible conectar con BIOMAC API.", 0);
    }
    if (!response.ok) {
      let envelope: ErrorEnvelopeDto | undefined;
      try {
        envelope = (await response.json()) as ErrorEnvelopeDto;
      } catch {
        envelope = undefined;
      }
      throw new BiomacApiError(
        envelope?.error?.message || "BIOMAC API no pudo completar la solicitud.",
        response.status,
        envelope?.error?.code,
        envelope?.error?.request_id,
        envelope?.error?.details,
      );
    }
    return response;
  }

  private resolveBaseUrl(): string {
    return typeof this.baseUrl === "function" ? this.baseUrl() : this.baseUrl;
  }

  private async json(response: Response): Promise<unknown> {
    try {
      return await response.json();
    } catch {
      throw this.invalidPayload(response.status);
    }
  }

  private invalidPayload(status: number): BiomacApiError {
    return new BiomacApiError(
      "BIOMAC API devolvió una respuesta inválida.",
      status,
      "INVALID_RESPONSE",
    );
  }
}
