// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DengueRepository } from "@/services/dengue";
import type { PredictionSnapshot } from "@/types/dengue";
import { useDengueDashboard } from "./useDengueDashboard";

const snapshot: PredictionSnapshot = {
  runId: "run-1",
  generatedAt: "2026-09-03T12:00:00Z",
  referenceMonth: "2026-08",
  sourceFileSha256: "sha",
  champion: {
    name: "biomac",
    version: "v1",
    outputType: "probability",
    supportedHorizons: ["T+1", "T+2"],
    featureContractVersion: "c1",
    featureContractSha256: "csha",
  },
  predictions: [
    {
      divipola: "68001",
      municipality: "Bucaramanga",
      horizon: "T+1",
      targetMonth: "2026-09",
      outputType: "probability",
      probability: 0.7,
      expectedCases: null,
      riskScore: null,
      label: "EXCESO",
      decisionThreshold: 0.61,
    },
    {
      divipola: "76001",
      municipality: "Cali",
      horizon: "T+2",
      targetMonth: "2026-10",
      outputType: "probability",
      probability: 0.4,
      expectedCases: null,
      riskScore: null,
      label: "NO_EXCESO",
      decisionThreshold: 0.67,
    },
  ],
};

function setup(
  create = vi.fn().mockResolvedValue({
    runId: "run-2",
    referenceMonth: "2026-08",
    status: "COMPLETED",
  }),
) {
  const getLatest = vi.fn().mockResolvedValue(snapshot);
  const repository: DengueRepository = { getLatest, createMonthlyRun: create };
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { ...renderHook(() => useDengueDashboard(repository), { wrapper }), getLatest, create };
}

afterEach(cleanup);

describe("useDengueDashboard", () => {
  it("opens with one latest GET and filters Bucaramanga/Cali locally", async () => {
    const { result, getLatest } = setup();
    await waitFor(() => expect(result.current.latest.isSuccess).toBe(true));
    expect(getLatest).toHaveBeenCalledOnce();
    expect(result.current.predictions?.[0]?.divipola).toBe("68001");
    act(() => result.current.setSelectedCity("76001"));
    expect(result.current.predictions?.[0]?.divipola).toBe("76001");
  });

  it("Refresh calls latest GET and never POST", async () => {
    const { result, getLatest, create } = setup();
    await waitFor(() => expect(result.current.latest.isSuccess).toBe(true));
    await act(async () => {
      await result.current.refresh();
    });
    expect(getLatest).toHaveBeenCalledTimes(2);
    expect(create).not.toHaveBeenCalled();
  });

  it("POST COMPLETED invalidates and refetches latest", async () => {
    const { result, getLatest, create } = setup();
    await waitFor(() => expect(result.current.latest.isSuccess).toBe(true));
    const file = new File(["data"], "monthly.csv");
    await act(async () => {
      await result.current.upload.mutateAsync({ file, referenceMonth: "2026-08" });
    });
    expect(create).toHaveBeenCalledWith(file, "2026-08");
    await waitFor(() => expect(getLatest).toHaveBeenCalledTimes(2));
  });

  it("POST error preserves snapshot and retry reuses file/month", async () => {
    const create = vi.fn().mockRejectedValue(new Error("upload failed"));
    const { result } = setup(create);
    await waitFor(() => expect(result.current.latest.isSuccess).toBe(true));
    const file = new File(["data"], "monthly.csv");
    const variables = { file, referenceMonth: "2026-08" };
    await act(async () => {
      await result.current.upload.mutateAsync(variables).catch(() => undefined);
    });
    expect(result.current.snapshot?.runId).toBe("run-1");
    await act(async () => {
      await result.current.upload.mutateAsync(variables).catch(() => undefined);
    });
    expect(create).toHaveBeenNthCalledWith(1, file, "2026-08");
    expect(create).toHaveBeenNthCalledWith(2, file, "2026-08");
    expect(result.current.snapshot?.runId).toBe("run-1");
  });
});
