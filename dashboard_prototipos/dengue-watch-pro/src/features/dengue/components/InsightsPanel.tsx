import { ShieldAlert } from "lucide-react";
import { Panel } from "@/components/atoms/Panel";
import { RiskDot } from "@/components/atoms/RiskText";
import type { Insight } from "@/types/dengue";

interface Props {
  insights: Insight[];
  recommendation: string;
}

export function InsightsPanel({ insights, recommendation }: Props) {
  return (
    <Panel title="7. Insights y recomendaciones">
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <ul className="grid gap-4 sm:grid-cols-3">
          {insights.slice(0, 3).map((insight) => (
            <li key={insight.id} className="flex gap-2.5">
              <span className="mt-1.5">
                <RiskDot level={insight.level} />
              </span>
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">{insight.title}:</span>{" "}
                {insight.detail}
              </p>
            </li>
          ))}
        </ul>
        <div className="rounded-lg border border-border bg-secondary/40 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-primary">
            <ShieldAlert className="size-4" />
            Recomendación
          </p>
          <p className="mt-2 text-sm text-muted-foreground">{recommendation}</p>
        </div>
      </div>
    </Panel>
  );
}
