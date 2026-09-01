import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { dengueRepository } from "@/services/dengue";
import type { CityId, DashboardData } from "@/types/dengue";

export function useDengueDashboard() {
  const [selectedCity, setSelectedCity] = useState<CityId>("bucaramanga");

  const query = useQuery<DashboardData>({
    queryKey: ["dengue", "dashboard"],
    queryFn: () => dengueRepository.getDashboard(),
    staleTime: 5 * 60 * 1000,
  });

  const data = query.data;
  const forecast = data?.forecasts[selectedCity];

  return {
    isLoading: query.isLoading,
    data,
    forecast,
    selectedCity,
    setSelectedCity,
  };
}
