export interface LegendItem {
  label: string;
  color: string;
  shape?: "line" | "dashed" | "area" | "dot";
}

export function ChartLegend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <Marker item={item} />
          <span>{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

function Marker({ item }: { item: LegendItem }) {
  const shape = item.shape ?? "line";
  if (shape === "dot") {
    return <span className="size-2.5 rounded-full" style={{ backgroundColor: item.color }} />;
  }
  if (shape === "area") {
    return (
      <span
        className="h-2.5 w-4 rounded-sm"
        style={{ backgroundColor: item.color, opacity: 0.8 }}
      />
    );
  }
  return (
    <span
      className="h-0 w-5"
      style={{
        borderTopWidth: 2,
        borderTopStyle: shape === "dashed" ? "dashed" : "solid",
        borderTopColor: item.color,
      }}
    />
  );
}
