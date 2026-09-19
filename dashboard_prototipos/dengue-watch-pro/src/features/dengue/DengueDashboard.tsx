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
      <div className="mt-4 border-t pt-3 text-sm">
        <p className="font-medium">
          {prediction.explanation?.available
            ? prediction.explanation.method === "shap" && prediction.explanation.scope === "local"
              ? "SHAP local"
              : `Explicación ${prediction.explanation.method ?? "local"}`
            : "Explicación local no disponible para esta predicción."}
        </p>
        {prediction.explanation?.available ? (
          <ul className="mt-2 space-y-1">
            {prediction.explanation.topFeatures.map((feature) => (
              <li key={feature.feature}>
                {feature.feature}: {feature.contribution > 0 ? "+" : ""}
                {feature.contribution} — contribución al resultado del modelo
                {feature.value === null ? "" : ` (valor ${feature.value})`}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
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
  const { latest, history, upload, snapshot, predictions, selectedCity, setSelectedCity, refresh } =
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
          <h1 className="text-2xl font-bold">BIOMAC — Sistema de alerta temprana de dengue</h1>
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
      <Panel title="Metadata y trazabilidad">
        <dl className="grid gap-2 text-sm md:grid-cols-3">
          <Value label="Output" value={snapshot.champion.outputType} />
          <Value label="Feature contract" value={snapshot.champion.featureContractVersion} />
          <Value label="Run" value={snapshot.runId} />
        </dl>
      </Panel>
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
          {snapshot.currentStatus?.[selectedCity] ? (
            <dl className="grid gap-2 text-sm">
              <Value
                label="Casos observados"
                value={snapshot.currentStatus[selectedCity]?.observedCases ?? null}
              />
              <Value label="P25" value={snapshot.currentStatus[selectedCity]?.p25 ?? null} />
              <Value label="P50" value={snapshot.currentStatus[selectedCity]?.p50 ?? null} />
              <Value label="P75" value={snapshot.currentStatus[selectedCity]?.p75 ?? null} />
              <Value
                label="Zona"
                value={snapshot.currentStatus[selectedCity]?.endemicZone ?? null}
              />
            </dl>
          ) : (
            <p className="text-sm text-muted-foreground">Información de contexto no disponible.</p>
          )}
        </Panel>
        <Panel title="Explicabilidad">
          <p className="text-sm text-muted-foreground">
            La explicación se presenta por horizonte junto a cada predicción y describe
            contribuciones del modelo, no causalidad.
          </p>
        </Panel>
        <Panel title="Calidad de datos">
          {snapshot.dataQuality ? (
            <div className="text-sm">
              <p>Estado: {snapshot.dataQuality.status}</p>
              <p>Último mes observado: {snapshot.dataQuality.lastObservedMonth}</p>
              {snapshot.dataQuality.warnings.map((warning) => (
                <p role="alert" className="mt-2 text-amber-700" key={warning}>
                  {warning}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Información de calidad no disponible.</p>
          )}
        </Panel>
      </section>
      <Panel title="Historial de predicciones">
        {history.data?.length ? (
          <ul className="space-y-1 text-sm">
            {history.data.map((item) => (
              <li key={item.runId}>
                {item.referenceMonth} · Run {item.runId}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            No hay historial de predicciones disponible.
          </p>
        )}
      </Panel>
    </main>
  );
}
