import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartLegend } from "@/components/atoms/ChartLegend";
import { Panel } from "@/components/atoms/Panel";
import { formatMonth, formatShortMonth } from "@/lib/dengue-format";
import type { CityForecast } from "@/types/dengue";

export function HistoricalSeriesChart({ forecast }: { forecast: CityForecast }) {
  const data = useMemo(() => {
    const series = forecast.series;
    const lastObservedIndex = series.reduce(
      (acc, p, i) => (p.observed !== null ? i : acc),
      0,
    );
    const lastObserved = series[lastObservedIndex]?.observed ?? 0;
    const t1 = forecast.predictions["T+1"];
    const t2 = forecast.predictions["T+2"];

    return series.map((point, i) => {
      const forecastFactor =
        i === lastObservedIndex + 1
          ? 1 + t1.probability * 0.35
          : i === lastObservedIndex + 2
            ? 1 + t2.probability * 0.55
            : null;

      return {
        ...point,
        band: point.p75 - point.p25,
        excess: point.isExcess ? point.observed : null,
        projected:
          i === lastObservedIndex
            ? point.observed
            : forecastFactor !== null
              ? Math.round(lastObserved * forecastFactor)
              : null,
      };
    });
  }, [forecast]);

  const forecastStart = data.find((d) => d.isForecast)?.month;

  return (
    <Panel
      title={`4. Serie histórica y canal endémico — ${forecast.city.name}`}
      footer="Fuente: datos mock desacoplados • Reemplazables por la API del modelo."
    >
      <ChartLegend
        items={[
          { label: "Casos observados", color: "var(--series-observed)" },
          { label: "P50 (mediana)", color: "var(--muted-foreground)", shape: "dashed" },
          { label: "P75 (umbral)", color: "var(--risk-medium)", shape: "dashed" },
          { label: "Rango endémico (P25–P75)", color: "var(--channel-band)", shape: "area" },
          { label: "Exceso histórico", color: "var(--risk-high)", shape: "dot" },
          { label: "Pronóstico", color: "var(--risk-high)", shape: "dashed" },
        ]}
      />
      <div className="mt-4 h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -12 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="month"
              tickFormatter={(m: string) => formatShortMonth(m)}
              tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
              interval={1}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
            />
            <YAxis
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={48}
              label={{
                value: "Casos de dengue grave",
                angle: -90,
                position: "insideLeft",
                fill: "var(--muted-foreground)",
                fontSize: 11,
              }}
            />
            <Tooltip
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--popover-foreground)",
              }}
              labelFormatter={(m: string) => formatMonth(m)}
              formatter={(value: number, name: string) => [value, name]}
            />
            {forecastStart ? (
              <ReferenceArea
                x1={forecastStart}
                x2={data[data.length - 1]?.month}
                fill="var(--muted)"
                fillOpacity={0.35}
              />
            ) : null}
            <Area
              dataKey="p25"
              stackId="channel"
              stroke="none"
              fill="transparent"
              name="P25"
              isAnimationActive={false}
            />
            <Area
              dataKey="band"
              stackId="channel"
              stroke="none"
              fill="var(--channel-band)"
              fillOpacity={0.85}
              name="Rango P25–P75"
              isAnimationActive={false}
            />
            <Line
              dataKey="p50"
              stroke="var(--muted-foreground)"
              strokeDasharray="5 4"
              dot={false}
              name="P50"
            />
            <Line
              dataKey="p75"
              stroke="var(--risk-medium)"
              strokeDasharray="6 4"
              dot={false}
              name="P75"
            />
            <Line
              dataKey="observed"
              stroke="var(--series-observed)"
              strokeWidth={2.5}
              dot={false}
              name="Casos observados"
              connectNulls={false}
            />
            <Line
              dataKey="projected"
              stroke="var(--risk-high)"
              strokeWidth={2.5}
              strokeDasharray="5 3"
              dot={{ r: 3, fill: "var(--risk-high)" }}
              name="Pronóstico"
              connectNulls
            />
            <Scatter dataKey="excess" fill="var(--risk-high)" name="Exceso histórico" />
            {forecastStart ? (
              <ReferenceLine
                x={forecastStart}
                stroke="var(--muted-foreground)"
                strokeDasharray="4 4"
                label={{
                  value: "Pronóstico",
                  position: "insideTopRight",
                  fill: "var(--muted-foreground)",
                  fontSize: 11,
                }}
              />
            ) : null}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
