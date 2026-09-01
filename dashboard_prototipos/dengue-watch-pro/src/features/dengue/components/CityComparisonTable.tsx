import { Panel } from "@/components/atoms/Panel";
import { RiskDot, riskFromProbability, riskTextClass } from "@/components/atoms/RiskText";
import { formatPercent, labelText } from "@/lib/dengue-format";
import { cn } from "@/lib/utils";
import type { CityForecast, CityId } from "@/types/dengue";

interface Props {
  forecasts: CityForecast[];
  selectedCity: CityId;
  onSelect: (city: CityId) => void;
}

export function CityComparisonTable({ forecasts, selectedCity, onSelect }: Props) {
  return (
    <Panel title="Comparativo de ciudades (T+1 / T+2)">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="pb-2 text-left font-medium">Ciudad</th>
            <th className="pb-2 text-right font-medium">T+1</th>
            <th className="pb-2 text-right font-medium">Prob. T+1</th>
            <th className="pb-2 text-right font-medium">T+2</th>
            <th className="pb-2 text-right font-medium">Prob. T+2</th>
          </tr>
        </thead>
        <tbody>
          {forecasts.map((f) => {
            const t1 = f.predictions["T+1"];
            const t2 = f.predictions["T+2"];
            const l1 = riskFromProbability(t1.probability);
            const l2 = riskFromProbability(t2.probability);
            return (
              <tr
                key={f.city.id}
                onClick={() => onSelect(f.city.id)}
                className={cn(
                  "cursor-pointer border-t border-border/70 transition-colors hover:bg-secondary/40",
                  f.city.id === selectedCity && "bg-secondary/50",
                )}
              >
                <td className="py-3">
                  <span className="flex items-center gap-2 font-medium">
                    <RiskDot level={l2} />
                    {f.city.name}
                  </span>
                </td>
                <td className={cn("py-3 text-right font-semibold", riskTextClass[l1])}>
                  {labelText(t1.label)}
                </td>
                <td className={cn("py-3 text-right", riskTextClass[l1])}>
                  {formatPercent(t1.probability)}
                </td>
                <td className={cn("py-3 text-right font-semibold", riskTextClass[l2])}>
                  {labelText(t2.label)}
                </td>
                <td className={cn("py-3 text-right", riskTextClass[l2])}>
                  {formatPercent(t2.probability)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
