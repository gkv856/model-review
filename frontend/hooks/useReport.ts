"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface IUseReport {
  jobId: string;
  enabled: boolean;
}

// Input: jobId, enabled flag (should only fetch after job completes)
// Output: query result with full IReport data
export const useReport = (props: IUseReport) => {
  const { jobId, enabled } = props;

  const query = useQuery({
    queryKey: ["report", jobId],
    queryFn: () => api.getReport({ jobId }),
    enabled: enabled && !!jobId,
    staleTime: Infinity,
  });

  return query;
};
