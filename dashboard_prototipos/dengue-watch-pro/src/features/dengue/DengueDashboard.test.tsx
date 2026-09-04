// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDengueDashboard } from "@/hooks/useDengueDashboard";
import { BiomacApiError } from "@/services/dengue";
import { DengueDashboard } from "./DengueDashboard";

vi.mock("@/hooks/useDengueDashboard", () => ({ useDengueDashboard: vi.fn() }));
vi.mock("./components/MonthlyUploadDialog", () => ({ MonthlyUploadDialog: () => null }));

const snapshot = {
  runId: "run-1",
  generatedAt: "2026-09-03T12:00:00Z",
  referenceMonth: "2026-08",
  sourceFileSha256: "sha",
  champion: {
    name: "biomac",
    version: "v1",
    outputType: "probability",
    supportedHorizons: ["T+1", "T+2"] as const,
    featureContractVersion: "c1",
    featureContractSha256: "csha",
  },
  predictions: [
    {
      divipola: "68001" as const,
      municipality: "Bucaramanga",
      horizon: "T+1" as const,
      targetMonth: "2026-09",
      outputType: "probability",
      probability: 0.72,
      expectedCases: null,
      riskScore: null,
      label: "EXCESO",
      decisionThreshold: 0.61,
    },
  ],
};

function dashboardState(overrides: Record<string, unknown> = {}) {
  return {
    latest: { isPending: false, isFetching: false, isError: false, error: null, refetch: vi.fn() },
    upload: { isPending: false, data: undefined, error: null, mutate: vi.fn() },
    snapshot,
    predictions: snapshot.predictions,
    selectedCity: "68001",
    setSelectedCity: vi.fn(),
    refresh: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useDengueDashboard>;
}

describe("DengueDashboard states", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(cleanup);

  it("announces initial loading without rendering mock data", () => {
    vi.mocked(useDengueDashboard).mockReturnValue(
      dashboardState({
        latest: { isPending: true },
        snapshot: undefined,
        predictions: undefined,
      }),
    );
    render(<DengueDashboard />);
    expect(screen.getByRole("status")).toHaveTextContent("Cargando predicciones");
  });

  it("maps only PREDICTION_NOT_FOUND to the empty state", () => {
    const error = new BiomacApiError("Sin predicción", 404, "PREDICTION_NOT_FOUND");
    vi.mocked(useDengueDashboard).mockReturnValue(
      dashboardState({
        latest: { isPending: false, error, refetch: vi.fn() },
        snapshot: undefined,
        predictions: undefined,
      }),
    );
    render(<DengueDashboard />);
    expect(screen.getByText(/Aún no hay predicciones disponibles/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("renders real nullable values without converting them", () => {
    vi.mocked(useDengueDashboard).mockReturnValue(dashboardState());
    render(<DengueDashboard />);
    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.getAllByText("No disponible")).toHaveLength(2);
    expect(screen.getAllByText("Información no disponible en esta versión.")).toHaveLength(3);
  });

  it("refreshes latest and preserves stale content on a refresh error", () => {
    const refresh = vi.fn();
    vi.mocked(useDengueDashboard).mockReturnValue(
      dashboardState({
        latest: {
          isPending: false,
          isFetching: false,
          isError: true,
          error: new Error("offline"),
          refetch: vi.fn(),
        },
        refresh,
      }),
    );
    render(<DengueDashboard />);
    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.getByText(/Se conserva la última predicción válida/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Actualizar vista" }));
    expect(refresh).toHaveBeenCalledOnce();
  });
});
