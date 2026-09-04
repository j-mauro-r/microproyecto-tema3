import { useState } from "react";
import { LoaderCircle, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { MonthlyRunReceipt } from "@/types/dengue";

interface Props {
  isSubmitting: boolean;
  receipt: MonthlyRunReceipt | undefined;
  errorMessage: string | undefined;
  onSubmit: (file: File, referenceMonth: string) => void;
}

export function MonthlyUploadDialog({ isSubmitting, receipt, errorMessage, onSubmit }: Props) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File>();
  const [referenceMonth, setReferenceMonth] = useState("");
  const [validation, setValidation] = useState<string>();
  const submit = () => {
    if (!file || !file.name.toLowerCase().endsWith(".csv")) {
      setValidation("Selecciona un archivo CSV válido.");
      return;
    }
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(referenceMonth)) {
      setValidation("Selecciona un mes válido.");
      return;
    }
    setValidation(undefined);
    if (window.confirm(`¿Actualizar BIOMAC con ${file.name} para ${referenceMonth}?`)) {
      onSubmit(file, referenceMonth);
    }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Upload />
          Actualizar datos
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Actualizar periodo mensual</DialogTitle>
          <DialogDescription>La API validará y procesará el CSV seleccionado.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="monthly-file">Archivo mensual CSV</Label>
            <Input
              id="monthly-file"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => setFile(event.target.files?.[0])}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="reference-month">Mes de referencia</Label>
            <Input
              id="reference-month"
              type="month"
              value={referenceMonth}
              onChange={(event) => setReferenceMonth(event.target.value)}
            />
          </div>
          {validation ? (
            <p role="alert" className="text-sm text-destructive">
              {validation}
            </p>
          ) : null}
          {errorMessage ? (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage}
            </p>
          ) : null}
          {receipt ? (
            <p role="status" className="text-sm text-primary">
              Actualización completada: {receipt.runId} · {receipt.referenceMonth} ·{" "}
              {receipt.status}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button type="button" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <LoaderCircle className="animate-spin" /> : null}
            {isSubmitting ? "Procesando…" : errorMessage ? "Reintentar" : "Confirmar actualización"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
