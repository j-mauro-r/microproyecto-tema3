import { createFileRoute } from "@tanstack/react-router";
import { DengueDashboard } from "@/features/dengue/DengueDashboard";

const title = "BIOMAC — Alerta temprana de dengue grave";
const description =
  "Dashboard de alerta temprana de exceso de casos de dengue grave en Bucaramanga y Cali, con horizonte de 1 a 2 meses.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DengueDashboard,
});
