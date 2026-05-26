"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

interface ISubmitArgs {
  modelFile: File;
  mapFile: File;
}

// Input: modelFile, mapFile via mutate()
// Output: mutation state + auto-navigates to /results/{jobId} on success
export const useReview = () => {
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: async (args: ISubmitArgs) => {
      const { modelFile, mapFile } = args;
      return api.submitReview({ modelFile, mapFile });
    },
    onSuccess: (data) => {
      router.push(`/results/${data.job_id}/pipeline`);
    },
  });

  return mutation;
};
