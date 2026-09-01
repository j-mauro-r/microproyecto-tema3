import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type RiskLevel = "high" | "medium" | "low";

export const riskTextClass: Record<RiskLevel, string> = {
  high: "text-risk-high",
  medium: "text-risk-medium",
  low: "text-risk-low",
};

export const riskBgClass: Record<RiskLevel, string> = {
  high: "bg-risk-high",
  medium: "bg-risk-medium",
  low: "bg-risk-low",
};

/** Traduce una probabilidad a nivel de riesgo con el umbral de decisión del modelo. */
export function riskFromProbability(probability: number, threshold = 0.5): RiskLevel {
  if (probability >= threshold) return "high";
  if (probability >= threshold * 0.7) return "medium";
  return "low";
}

export function RiskText({
  level,
  className,
  children,
}: {
  level: RiskLevel;
  className?: string;
  children: ReactNode;
}) {
  return <span className={cn(riskTextClass[level], className)}>{children}</span>;
}

export function RiskDot({ level }: { level: RiskLevel }) {
  return <span className={cn("inline-block size-2.5 rounded-full", riskBgClass[level])} />;
}
