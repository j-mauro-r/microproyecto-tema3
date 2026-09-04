// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MonthlyUploadDialog } from "./MonthlyUploadDialog";

function renderDialog(overrides: Partial<Parameters<typeof MonthlyUploadDialog>[0]> = {}) {
  const onSubmit = vi.fn();
  render(
    <MonthlyUploadDialog
      isSubmitting={false}
      receipt={undefined}
      errorMessage={undefined}
      onSubmit={onSubmit}
      {...overrides}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Actualizar datos" }));
  return onSubmit;
}

function chooseFile(name = "monthly.csv") {
  const file = new File(["data"], name, { type: "text/csv" });
  fireEvent.change(screen.getByLabelText("Archivo mensual CSV"), { target: { files: [file] } });
  return file;
}

describe("MonthlyUploadDialog", () => {
  const confirmMock = vi.fn<() => boolean>();

  beforeEach(() => {
    confirmMock.mockReset();
    confirmMock.mockReturnValue(true);
    Object.defineProperty(window, "confirm", {
      configurable: true,
      writable: true,
      value: confirmMock,
    });
  });
  afterEach(cleanup);

  it("does not submit without file, month, or with a non-CSV file", () => {
    const onSubmit = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar actualización" }));
    expect(onSubmit).not.toHaveBeenCalled();
    chooseFile("monthly.txt");
    fireEvent.click(screen.getByRole("button", { name: "Confirmar actualización" }));
    expect(onSubmit).not.toHaveBeenCalled();
    chooseFile();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar actualización" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("cancels confirmation without POST and submits exact file/month when accepted", () => {
    const onSubmit = renderDialog();
    const file = chooseFile();
    fireEvent.change(screen.getByLabelText("Mes de referencia"), { target: { value: "2026-08" } });
    confirmMock.mockReturnValueOnce(false);
    fireEvent.click(screen.getByRole("button", { name: "Confirmar actualización" }));
    expect(onSubmit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar actualización" }));
    expect(onSubmit).toHaveBeenCalledWith(file, "2026-08");
  });

  it("disables submit while pending", () => {
    renderDialog({ isSubmitting: true });
    expect(screen.getByRole("button", { name: /Procesando/ })).toBeDisabled();
  });

  it("shows receipt and keeps retry action on error", () => {
    renderDialog({
      receipt: { runId: "run-9", referenceMonth: "2026-08", status: "COMPLETED" },
      errorMessage: "Carga rechazada",
    });
    expect(screen.getByRole("status")).toHaveTextContent("run-9 · 2026-08 · COMPLETED");
    expect(screen.getByRole("alert")).toHaveTextContent("Carga rechazada");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
