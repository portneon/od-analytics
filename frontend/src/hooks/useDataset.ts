import { useQuery } from '@tanstack/react-query'
import { getDataset } from '@/services/datasets'

const ACTIVE_STATUSES = new Set(['UPLOADING', 'QUEUED', 'PROCESSING'])

/** Polls while the dataset is still being ingested/processed; stops once it
 * reaches a terminal status (COMPLETED/PARTIAL/FAILED) so we're not polling
 * a finished dataset forever. */
export function useDataset(datasetId: string | undefined) {
  return useQuery({
    queryKey: ['dataset', datasetId],
    queryFn: () => getDataset(datasetId!),
    enabled: !!datasetId,
    refetchInterval: (query) => (query.state.data && ACTIVE_STATUSES.has(query.state.data.status) ? 2000 : false),
  })
}
