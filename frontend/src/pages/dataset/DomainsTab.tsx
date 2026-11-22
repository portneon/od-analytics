import { useOutletContext } from 'react-router-dom'
import { channelLabels } from '@/utils/channel'
import type { Dataset } from '@/types/api'
import { EntityListTab } from './EntityListTab'

export function DomainsTab() {
  const { dataset } = useOutletContext<{ dataset: Dataset }>()
  const labels = channelLabels(dataset.source)
  return <EntityListTab kind="domains" nameLabel={labels.domainLabelPlural} />
}
