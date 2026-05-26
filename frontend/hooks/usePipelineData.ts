"use client"

import { useEffect, useRef, useState } from "react"
import {
  PIPELINE_STEPS,
  IStepData,
  aggregateStep,
  parseCSV,
  parseStructureJSON,
} from "@/lib/pipelineSteps"

interface IUsePipelineData {
  jobId: string
  jobComplete: boolean
}

// Maps filename → step data. Fetches each file once when it first appears.
export function usePipelineData(props: IUsePipelineData) {
  const { jobId, jobComplete } = props

  const [stepData, setStepData] = useState<Record<string, IStepData>>(() =>
    Object.fromEntries(
      PIPELINE_STEPS.map((s) => [
        s.id,
        { status: "pending", headers: [], rows: [], stats: [], sizeBytes: 0 },
      ])
    )
  )

  // Track which files we've already fetched so we don't re-fetch
  const fetchedFiles = useRef<Set<string>>(new Set())
  const pollingRef   = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchFile = async (stepId: string, filename: string, sizeBytes: number) => {
    if (fetchedFiles.current.has(filename)) return
    fetchedFiles.current.add(filename)

    setStepData((prev) => ({
      ...prev,
      [stepId]: { ...prev[stepId], status: "loading" },
    }))

    try {
      const res = await fetch(`/api/interim/${jobId}/${filename}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const text = await res.text()

      const step = PIPELINE_STEPS.find((s) => s.id === stepId)!
      const { headers, rows } =
        step.fileType === "json" ? parseStructureJSON(text) : parseCSV(text)
      const stats = aggregateStep(step, rows, text)

      setStepData((prev) => ({
        ...prev,
        [stepId]: { status: "ready", headers, rows, stats, sizeBytes },
      }))
    } catch {
      // Revert to pending so it can be retried next poll
      fetchedFiles.current.delete(filename)
      setStepData((prev) => ({
        ...prev,
        [stepId]: { ...prev[stepId], status: "pending" },
      }))
    }
  }

  const poll = async () => {
    try {
      const res = await fetch(`/api/interim/${jobId}`)
      if (!res.ok) return
      const data = (await res.json()) as { files: { name: string; size_bytes: number }[] }

      for (const file of data.files ?? []) {
        const step = PIPELINE_STEPS.find((s) => s.filename === file.name)
        if (step && !fetchedFiles.current.has(file.name)) {
          fetchFile(step.id, file.name, file.size_bytes)
        }
      }
    } catch {
      // Swallow — next tick will retry
    }
  }

  useEffect(() => {
    poll()

    pollingRef.current = setInterval(poll, 2000)

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  // Stop polling once all files are loaded (works for both live and past runs)
  useEffect(() => {
    const allReady = PIPELINE_STEPS.every(
      (s) => stepData[s.id]?.status === "ready"
    )
    if (allReady && pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [stepData])

  const readyCount = PIPELINE_STEPS.filter((s) => stepData[s.id]?.status === "ready").length

  return { stepData, readyCount, total: PIPELINE_STEPS.length }
}
