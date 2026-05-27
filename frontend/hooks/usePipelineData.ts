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
  const [firstPollDone, setFirstPollDone] = useState(false)

  const fetchedFiles  = useRef<Set<string>>(new Set())
  const pollingRef    = useRef<ReturnType<typeof setInterval> | null>(null)
  const firstPollRef  = useRef(false)

  const checkLlmErrors = async (stepId: string) => {
    if (stepId !== "11") return
    try {
      const res = await fetch(`/api/interim/${jobId}/11_llm_prompts.json`)
      if (!res.ok) return
      const prompts = (await res.json()) as Array<{ raw_response?: string }>
      const errored = prompts.find((p) => p.raw_response?.startsWith("[ERROR]"))
      if (errored) {
        setStepData((prev) => ({
          ...prev,
          "11": { ...prev["11"], status: "failed", error: errored.raw_response },
        }))
      }
    } catch {
      // ignore — prompts file may not exist yet
    }
  }

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

      // After step 11 loads, check whether any LLM batch returned an error
      checkLlmErrors(stepId)
    } catch {
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

      if (!firstPollRef.current) {
        firstPollRef.current = true
        setFirstPollDone(true)
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

  // Stop polling: all files loaded (ready or failed), or job ended (give 4s to catch stragglers)
  useEffect(() => {
    const allReady = PIPELINE_STEPS.every((s) => {
      const st = stepData[s.id]?.status
      return st === "ready" || st === "failed"
    })
    if (allReady && pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
      return
    }
    if (jobComplete && firstPollDone && pollingRef.current) {
      const timer = setTimeout(() => {
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
        }
      }, 4000)
      return () => clearTimeout(timer)
    }
  }, [stepData, jobComplete, firstPollDone])

  const readyCount  = PIPELINE_STEPS.filter((s) => stepData[s.id]?.status === "ready").length
  const failedCount = PIPELINE_STEPS.filter((s) => stepData[s.id]?.status === "failed").length
  const loadedCount = readyCount + failedCount

  return { stepData, readyCount, loadedCount, failedCount, total: PIPELINE_STEPS.length, firstPollDone }
}
