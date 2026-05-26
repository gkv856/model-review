"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface IUseJobStatus {
  jobId: string;
}

const POLL_INTERVAL_MS = 3000;

// Input: jobId
// Output: query result polling every 3s, stops when completed or failed
export const useJobStatus = (props: IUseJobStatus) => {
  const { jobId } = props;

  const query = useQuery({
    queryKey: ["status", jobId],
    queryFn: () => api.getStatus({ jobId }),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const isDone = status === "completed" || status === "failed";
      return isDone ? false : POLL_INTERVAL_MS;
    },
    enabled: !!jobId,
  });

  return query;
};
