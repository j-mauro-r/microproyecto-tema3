import { AlertCircle, LoaderCircle, RefreshCw } from "lucide-react";
import { Panel } from "@/components/atoms/Panel";
import { Button } from "@/components/ui/button";
import { useDengueDashboard } from "@/hooks/useDengueDashboard";
import { formatDateTime, formatMonth, formatPercent } from "@/lib/dengue-format";
import { BiomacApiError } from "@/services/dengue";
import type { MunicipalityCode, Prediction } from "@/types/dengue";
import { MonthlyUploadDialog } from "./components/MonthlyUploadDialog";

const CITIES: { code: MunicipalityCode; name: string }[] = [
  { code: "68001", name: "Bucaramanga" },
  { code: "76001", name: "Cali" },
];

function errorMessage(error: unknown): string {
  if (error instanceof BiomacApiError && error.status === 0) {
    return "No fue posible conectar con BIOMAC API.";
  }
  return error instanceof Error ? error.message : "No fue posible completar la operación.";
}

function PredictionCard({ prediction }: { prediction: Prediction }) {
  return (
    <Panel title={`${prediction.horizon} · ${formatMonth(prediction.targetMonth)}`}>
      <p className="text-3xl font-bold">{prediction.label ?? "Información no disponible"}</p>
      <dl className="mt-4 grid gap-2 text-sm">
        <Value
          label="Probabilidad"
          value={prediction.probability === null ? null : formatPercent(prediction.probability)}
        />
        <Value label="Casos esperados" value={prediction.expectedCases} />
        <Value label="Risk score" value={prediction.riskScore} />
        <Value label="Threshold" value={prediction.decisionThreshold} />
      </dl>
    </Panel>
  );
}

function Value({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value ?? "No disponible"}</dd>
    </div>
  );
}

export function DengueDashboard() {
  const { latest, upload, snapshot, predictions, selectedCity, setSelectedCity, refresh } =
    useDengueDashboard();
  const empty =
    latest.error instanceof BiomacApiError && latest.error.code === "PREDICTION_NOT_FOUND";

  if (latest.isPending) {
    return (
      <main
        role="status"
        className="flex min-h-screen items-center justify-center gap-2 text-muted-foreground"
      >
        <LoaderCircle className="animate-spin" /> Cargando predicciones…
      </main>
    );
  }
  if (!snapshot) {
    return (
      <main className="mx-auto flex min-h-screen max-w-2xl items-center px-5">
        <Panel title={empty ? "Sin predicciones" : "BIOMAC API no disponible"} className="w-full">
          <p>
            {empty
              ? "Aún no hay predicciones disponibles. Carga el primer periodo mensual para generar una predicción."
              : errorMessage(latest.error)}
          </p>
          <div className="mt-4 flex gap-3">
            <Button variant="outline" onClick={() => void latest.refetch()}>
              Reintentar
            </Button>
            <MonthlyUploadDialog
              isSubmitting={upload.isPending}
              receipt={upload.data}
              errorMessage={upload.error ? errorMessage(upload.error) : undefined}
              onSubmit={(file, referenceMonth) => upload.mutate({ file, referenceMonth })}
            />
          </div>
        </Panel>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-[1400px] flex-col gap-4 px-5 py-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">BIOMAC — Alerta temprana de dengue grave</h1>
          <p className="text-sm text-muted-foreground">
            Corte {snapshot.referenceMonth} · Champion {snapshot.champion.name}{" "}
            {snapshot.champion.version}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void refresh()} disabled={latest.isFetching}>
            <RefreshCw className={latest.isFetching ? "animate-spin" : ""} />
            {latest.isFetching ? "Actualizando…" : "Actualizar vista"}
          </Button>
          <MonthlyUploadDialog
            isSubmitting={upload.isPending}
            receipt={upload.data}
            errorMessage={upload.error ? errorMessage(upload.error) : undefined}
            onSubmit={(file, referenceMonth) => upload.mutate({ file, referenceMonth })}
          />
        </div>
      </header>

      {latest.isError ? (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-destructive/50 p-3 text-sm text-destructive"
        >
          <AlertCircle /> No se pudo actualizar la vista. Se conserva la última predicción válida.
          <Button size="sm" variant="outline" onClick={() => void refresh()}>
            Reintentar
          </Button>
        </div>
      ) : null}

      <div className="text-xs text-muted-foreground">
        Actualizado {formatDateTime(snapshot.generatedAt)} · Run {snapshot.runId}
      </div>
      <div className="flex gap-2" role="radiogroup" aria-label="Ciudad">
        {CITIES.map((city) => (
          <Button
            key={city.code}
            role="radio"
            aria-checked={selectedCity === city.code}
            variant={selectedCity === city.code ? "default" : "outline"}
            onClick={() => setSelectedCity(city.code)}
          >
            {city.name}
          </Button>
        ))}
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        {(predictions ?? []).map((prediction) => (
          <PredictionCard key={prediction.horizon} prediction={prediction} />
        ))}
      </section>
      {predictions?.length === 0 ? (
        <Panel>
          <p>No hay predicciones persistidas para esta ciudad.</p>
        </Panel>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <Panel title="Canal endémico">
          <p className="text-sm text-muted-foreground">
            Información no disponible en esta versión.
          </p>
        </Panel>
        <Panel title="Explicabilidad">
          <p className="text-sm text-muted-foreground">
            Información no disponible en esta versión.
          </p>
        </Panel>
        <Panel title="Historia y calidad">
          <p className="text-sm text-muted-foreground">
            Información no disponible en esta versión.
          </p>
        </Panel>
      </section>
    </main>
  );
}
