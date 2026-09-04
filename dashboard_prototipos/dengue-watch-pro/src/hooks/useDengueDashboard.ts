import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { dengueRepository } from "@/services/dengue";
import type { DengueRepository } from "@/services/dengue";
import type { MunicipalityCode } from "@/types/dengue";

export const latestPredictionKey = ["biomac", "predictions", "latest"] as const;

export function useDengueDashboard(repository: DengueRepository = dengueRepository) {
  const queryClient = useQueryClient();
  const [selectedCity, setSelectedCity] = useState<MunicipalityCode>("68001");
  const latest = useQuery({
    queryKey: latestPredictionKey,
    queryFn: ({ signal }) => repository.getLatest(signal),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const upload = useMutation({
    mutationFn: ({ file, referenceMonth }: { file: File; referenceMonth: string }) =>
      repository.createMonthlyRun(file, referenceMonth),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: latestPredictionKey });
    },
  });
  return {
    latest,
    upload,
    snapshot: latest.data,
    predictions: latest.data?.predictions.filter(
      (prediction) => prediction.divipola === selectedCity,
    ),
    selectedCity,
    setSelectedCity,
    refresh: () => latest.refetch(),
  };
}
