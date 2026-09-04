import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { BiomacApiError, HttpDengueRepository } from "./dengue.http.repository";

const latest = {
  schema_version: "2.0.0",
  request_id: "request-1",
  prediction_snapshot: {
    run_id: "run-1",
    generated_at: "2026-09-03T12:00:00Z",
    reference_month: "2026-08",
    source_file_sha256: "sha",
    champion: {
      name: "biomac-champion",
      version: "v1",
      output_type: "expected_cases",
      supported_horizons: ["T+1", "T+2"],
      feature_contract_version: "c1",
      feature_contract_sha256: "csha",
    },
    predictions: [
      {
        divipola: "68001",
        municipality: "Bucaramanga",
        horizon: "T+1",
        target_month: "2026-09",
        output_type: "expected_cases",
        probability: null,
        expected_cases: 12.5,
        risk_score: 0.8,
        label: null,
        decision_threshold: null,
      },
      {
        divipola: "76001",
        municipality: "Cali",
        horizon: "T+2",
        target_month: "2026-10",
        output_type: "probability",
        probability: 0.72,
        expected_cases: null,
        risk_score: null,
        label: "EXCESO",
        decision_threshold: 0.67,
      },
    ],
  },
};

describe("HttpDengueRepository", () => {
  it("maps latest without fabricating nullable outputs", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(latest));
    const snapshot = await new HttpDengueRepository("https://api.test/api/v2", fetcher).getLatest();
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.test/api/v2/predictions/latest",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
    expect(snapshot.predictions[0]).toMatchObject({
      probability: null,
      expectedCases: 12.5,
      riskScore: 0.8,
      label: null,
      decisionThreshold: null,
    });
    expect(snapshot.predictions[1]?.decisionThreshold).toBe(0.67);
  });

  it("maps PREDICTION_NOT_FOUND without using a mock", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json(
        {
          error: {
            code: "PREDICTION_NOT_FOUND",
            message: "Sin predicción",
            request_id: "req-2",
          },
        },
        { status: 404 },
      ),
    );
    await expect(
      new HttpDengueRepository("https://api.test/api/v2", fetcher).getLatest(),
    ).rejects.toMatchObject({ status: 404, code: "PREDICTION_NOT_FOUND", requestId: "req-2" });
    expect(readFileSync(new URL("./index.ts", import.meta.url), "utf8")).not.toContain(
      "MockDengueRepository",
    );
  });

  it("sanitizes network and invalid JSON failures", async () => {
    const offline = vi.fn<typeof fetch>().mockRejectedValue(new Error("private network detail"));
    await expect(
      new HttpDengueRepository("https://api.test/api/v2", offline).getLatest(),
    ).rejects.toEqual(
      expect.objectContaining({ status: 0, message: "No fue posible conectar con BIOMAC API." }),
    );
    const invalid = vi.fn<typeof fetch>().mockResolvedValue(new Response("not json"));
    await expect(
      new HttpDengueRepository("https://api.test/api/v2", invalid).getLatest(),
    ).rejects.toBeInstanceOf(BiomacApiError);
  });

  it("rejects critical unsupported values", async () => {
    const payload = structuredClone(latest);
    payload.prediction_snapshot.predictions[0]!.horizon = "T+3";
    const repository = new HttpDengueRepository(
      "https://api.test/api/v2",
      vi.fn<typeof fetch>().mockResolvedValue(Response.json(payload)),
    );
    await expect(repository.getLatest()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });

  it("uploads browser FormData without setting multipart Content-Type", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json(
        {
          schema_version: "2.0.0",
          request_id: "request-1",
          run: { run_id: "run-2", status: "COMPLETED", reference_month: "2026-08" },
        },
        { status: 201 },
      ),
    );
    const file = new File(["data"], "monthly.csv", { type: "text/csv" });
    const receipt = await new HttpDengueRepository(
      "https://api.test/api/v2",
      fetcher,
    ).createMonthlyRun(file, "2026-08");
    const [, init] = fetcher.mock.calls[0]!;
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
    expect((init?.body as FormData).get("file")).toBe(file);
    expect((init?.body as FormData).get("reference_month")).toBe("2026-08");
    expect(init?.headers).toEqual({ Accept: "application/json" });
    expect(receipt).toEqual({ runId: "run-2", referenceMonth: "2026-08", status: "COMPLETED" });
  });
});
