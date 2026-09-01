import { AlertTriangle, ArrowDownRight, ArrowUpRight, ShieldCheck } from "lucide-react";
import { Panel } from "@/components/atoms/Panel";
import { riskFromProbability, riskTextClass } from "@/components/atoms/RiskText";
import { formatMonth, formatPercent, labelText } from "@/lib/dengue-format";
import { cn } from "@/lib/utils";
import type { EndemicChannelStatus, Prediction } from "@/types/dengue";

export function AlertCard({ prediction }: { prediction: Prediction }) {
  const excess = prediction.label === 1;
  const Icon = excess ? AlertTriangle : ShieldCheck;
  return (
    <Panel title={`1. Alerta ${prediction.horizon}`} accent={excess ? "high" : "low"}>
      <div className={cn("flex items-center gap-3", excess ? riskTextClass.high : riskTextClass.low)}>
        <Icon className="size-9" />
        <p className="text-4xl font-bold tracking-tight">{labelText(prediction.label)}</p>
      </div>
      <p className="mt-3 text-sm text-muted-foreground">
        {excess ? "Se espera exceso" : "No se espera exceso"} de casos de dengue grave en{" "}
        {prediction.horizon === "T+2" ? "2 meses" : "1 mes"} ({formatMonth(prediction.targetMonth)}).
      </p>
    </Panel>
  );
}

export function ProbabilityCard({
  prediction,
  previous,
}: {
  prediction: Prediction;
  previous: Prediction;
}) {
  const level = riskFromProbability(prediction.probability);
  const rising = prediction.probability >= previous.probability;
  const Trend = rising ? ArrowUpRight : ArrowDownRight;
  return (
    <Panel title={`2. Probabilidad de exceso (${prediction.horizon})`} accent={level}>
      <div className={cn("flex items-baseline gap-2", riskTextClass[level])}>
        <p className="text-5xl font-bold tracking-tight">
          {formatPercent(prediction.probability)}
        </p>
        <Trend className="size-7" />
      </div>
      <p className="mt-3 text-sm text-muted-foreground">
        {prediction.confidenceInterval
          ? `IC 95%: ${formatPercent(prediction.confidenceInterval[0])} – ${formatPercent(prediction.confidenceInterval[1])}`
          : null}
      </p>
      <p className="mt-1 text-xs text-muted-foreground/80">
        {rising ? "Al alza" : "A la baja"} frente a {previous.horizon} (
        {formatPercent(previous.probability)}).
      </p>
    </Panel>
  );
}

export function EndemicChannelCard({ status }: { status: EndemicChannelStatus }) {
  const level = status.ratioToP75 >= 1 ? "high" : status.ratioToP75 >= 0.85 ? "medium" : "low";
  return (
    <Panel title="3. Estado vs. canal endémico" accent={level}>
      <p className={cn("text-3xl font-bold tracking-tight", riskTextClass[level])}>
        {status.description}
      </p>
      <p className="mt-3 text-sm text-muted-foreground">
        Casos observados en {formatMonth(status.referenceMonth)} ({status.observedCases}) al{" "}
        {formatPercent(status.ratioToP75)} del P75 ({status.p75}).
      </p>
    </Panel>
  );
}
