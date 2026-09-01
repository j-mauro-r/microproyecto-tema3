import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PanelProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  accent?: "high" | "medium" | "low" | "none";
}

const accentClass: Record<NonNullable<PanelProps["accent"]>, string> = {
  high: "after:bg-risk-high",
  medium: "after:bg-risk-medium",
  low: "after:bg-risk-low",
  none: "after:bg-transparent",
};

export function Panel({
  title,
  subtitle,
  children,
  footer,
  className,
  accent = "none",
}: PanelProps) {
  return (
    <section
      className={cn(
        "relative flex flex-col rounded-xl border border-border bg-card p-5",
        "after:absolute after:inset-x-5 after:bottom-0 after:h-[3px] after:rounded-full",
        accentClass[accent],
        className,
      )}
    >
      {title ? (
        <header className="mb-3">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-1 text-xs text-muted-foreground/80">{subtitle}</p>
          ) : null}
        </header>
      ) : null}
      <div className="flex-1">{children}</div>
      {footer ? <div className="mt-4 text-xs text-muted-foreground">{footer}</div> : null}
    </section>
  );
}
