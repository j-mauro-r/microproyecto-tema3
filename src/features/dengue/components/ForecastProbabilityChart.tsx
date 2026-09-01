import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartLegend } from "@/components/atoms/ChartLegend";
import { Panel } from "@/components/atoms/Panel";
import { formatMonth } from "@/lib/dengue-format";
import type { CityForecast, Horizon } from "@/types/dengue";

const HORIZONS: Horizon[] = ["T+1", "T+2"];
const CITY_COLORS = ["var(--risk-high)", "var(--risk-medium)"];

export function ForecastProbabilityChart({ forecasts }: { forecasts: CityForecast[] }) {
  const data = HORIZONS.map((horizon) => {
    const targetMonth = forecasts[0]?.predictions[horizon].targetMonth;
    const row: Record<string, string | number> = {
      horizon: targetMonth ? `${horizon} (${formatMonth(targetMonth)})` : horizon,
    };
    forecasts.forEach((f) => {
      row[f.city.name] = Math.round(f.predictions[horizon].probability * 100);
    });
    return row;
  });

  return (
    <Panel
      title="5. Pronóstico de probabilidad de exceso"
      footer="Umbral de decisión para exceso: probabilidad ≥ 50%."
    >
      <ChartLegend
        items={forecasts.map((f, i) => ({
          label: f.city.name,
          color: CITY_COLORS[i % CITY_COLORS.length] ?? "var(--risk-high)",
          shape: "area",
        }))}
      />
      <div className="mt-4 h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 20, right: 8, bottom: 4, left: -12 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="horizon"
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={48}
              label={{
                value: "Probabilidad (%)",
                angle: -90,
                position: "insideLeft",
                fill: "var(--muted-foreground)",
                fontSize: 11,
              }}
            />
            <Tooltip
              cursor={{ fill: "var(--muted)", opacity: 0.3 }}
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--popover-foreground)",
              }}
              formatter={(v: number, name: string) => [`${v}%`, name]}
            />
            <ReferenceLine y={50} stroke="var(--muted-foreground)" strokeDasharray="5 4" />
            {forecasts.map((f, i) => (
              <Bar
                key={f.city.id}
                dataKey={f.city.name}
                fill={CITY_COLORS[i % CITY_COLORS.length] ?? "var(--risk-high)"}
                radius={[4, 4, 0, 0]}
                maxBarSize={54}
              >
                <LabelList
                  dataKey={f.city.name}
                  position="top"
                  formatter={(v: number) => `${v}%`}
                  fill={CITY_COLORS[i % CITY_COLORS.length] ?? "var(--risk-high)"}
                  fontSize={13}
                  fontWeight={700}
                />
                {data.map((_, idx) => (
                  <Cell key={idx} />
                ))}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
