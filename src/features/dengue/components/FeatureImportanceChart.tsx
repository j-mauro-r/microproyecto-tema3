import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "@/components/atoms/Panel";
import type { FeatureImportance } from "@/types/dengue";

const GROUP_COLOR: Record<FeatureImportance["group"], string> = {
  lag: "var(--risk-high)",
  climate: "var(--risk-medium)",
  seasonality: "var(--risk-low)",
};

export function FeatureImportanceChart({ features }: { features: FeatureImportance[] }) {
  const data = [...features].sort((a, b) => b.importance - a.importance);

  return (
    <Panel
      title="6. Variables que impulsan la predicción (SHAP)"
      subtitle="Importancia (SHAP promedio absoluto) — mayor valor = mayor impacto en el riesgo previsto."
    >
      <div className="mt-2 h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 40, bottom: 4, left: 8 }}
          >
            <CartesianGrid stroke="var(--border)" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, "dataMax"]}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
            />
            <YAxis
              type="category"
              dataKey="feature"
              width={160}
              tick={{ fill: "var(--foreground)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
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
              formatter={(v: number) => [v.toFixed(2), "Importancia"]}
            />
            <Bar dataKey="importance" radius={[0, 4, 4, 0]} maxBarSize={18}>
              {data.map((d) => (
                <Cell key={d.feature} fill={GROUP_COLOR[d.group]} />
              ))}
              <LabelList
                dataKey="importance"
                position="right"
                formatter={(v: number) => v.toFixed(2)}
                fill="var(--muted-foreground)"
                fontSize={11}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
