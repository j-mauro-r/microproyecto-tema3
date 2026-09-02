import { Activity } from "lucide-react";
import { formatDateTime } from "@/lib/dengue-format";

export function DashboardHeader({ updatedAt }: { updatedAt: string }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex items-center gap-3">
        <span className="flex size-11 items-center justify-center rounded-xl border border-border bg-card text-primary">
          <Activity className="size-6" />
        </span>
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-[28px]">
            BIOMAC — Alerta temprana de dengue grave
          </h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Colombia • Datos mensuales • Horizonte: 1–2 meses
          </p>
        </div>
      </div>
      <div className="text-right text-xs text-muted-foreground">
        <p>Última actualización</p>
        <p className="text-foreground">{formatDateTime(updatedAt)}</p>
      </div>
    </header>
  );
}
