import { apiPost } from './api'
import type { AskResult } from '@/types/api'

export function askQuestion(datasetId: string, question: string) {
  return apiPost<AskResult>(`/datasets/${datasetId}/ask`, { question })
}
