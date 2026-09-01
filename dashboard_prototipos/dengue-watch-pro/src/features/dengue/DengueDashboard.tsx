import { Panel } from "@/components/atoms/Panel";
import { useDengueDashboard } from "@/hooks/useDengueDashboard";
import {
  AlertCard,
  EndemicChannelCard,
  ProbabilityCard,
} from "./components/AlertKpiCards";
import { CityComparisonTable } from "./components/CityComparisonTable";
import { CitySelector } from "./components/CitySelector";
import { DashboardHeader } from "./components/DashboardHeader";
import { FeatureImportanceChart } from "./components/FeatureImportanceChart";
import { ForecastProbabilityChart } from "./components/ForecastProbabilityChart";
import { HistoricalSeriesChart } from "./components/HistoricalSeriesChart";
import { InsightsPanel } from "./components/InsightsPanel";

export function DengueDashboard() {
  const { data, forecast, selectedCity, setSelectedCity, isLoading } = useDengueDashboard();

  if (isLoading || !data || !forecast) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Cargando predicciones…
      </div>
    );
  }

  const allForecasts = data.cities.map((c) => data.forecasts[c.id]);

  return (
    <main className="mx-auto flex max-w-[1600px] flex-col gap-4 px-5 py-6">
      <DashboardHeader updatedAt={data.updatedAt} />

      <div className="grid gap-4 xl:grid-cols-[200px_repeat(3,minmax(0,1fr))_minmax(0,1.3fr)]">
        <Panel title="Ciudad">
          <CitySelector
            cities={data.cities}
            value={selectedCity}
            onChange={setSelectedCity}
          />
        </Panel>
        <AlertCard prediction={forecast.predictions["T+2"]} />
        <ProbabilityCard
          prediction={forecast.predictions["T+2"]}
          previous={forecast.predictions["T+1"]}
        />
        <EndemicChannelCard status={forecast.endemicChannel} />
        <CityComparisonTable
          forecasts={allForecasts}
          selectedCity={selectedCity}
          onSelect={setSelectedCity}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr_1fr]">
        <HistoricalSeriesChart forecast={forecast} />
        <ForecastProbabilityChart forecasts={allForecasts} />
        <FeatureImportanceChart features={forecast.featureImportances} />
      </div>

      <InsightsPanel
        insights={forecast.insights}
        recommendation={forecast.recommendation}
      />
    </main>
  );
}
