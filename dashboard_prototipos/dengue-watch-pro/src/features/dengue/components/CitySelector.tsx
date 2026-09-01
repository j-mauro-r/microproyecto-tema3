import { Building2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { City, CityId } from "@/types/dengue";

interface CitySelectorProps {
  cities: City[];
  value: CityId;
  onChange: (city: CityId) => void;
}

export function CitySelector({ cities, value, onChange }: CitySelectorProps) {
  return (
    <div className="flex flex-col gap-2" role="radiogroup" aria-label="Ciudad">
      {cities.map((city) => {
        const active = city.id === value;
        return (
          <button
            key={city.id}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(city.id)}
            className={cn(
              "flex items-center gap-3 rounded-lg border px-3 py-3 text-left text-sm font-medium transition-colors",
              active
                ? "border-primary bg-primary/15 text-foreground"
                : "border-border bg-secondary/40 text-muted-foreground hover:bg-secondary",
            )}
          >
            <span
              className={cn(
                "size-3 rounded-full border-2",
                active ? "border-primary bg-primary" : "border-muted-foreground",
              )}
            />
            <Building2 className="size-4 opacity-70" />
            {city.name}
          </button>
        );
      })}
    </div>
  );
}
