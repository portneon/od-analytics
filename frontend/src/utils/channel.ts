export type Channel = 'email' | 'whatsapp'

export function channelFromSource(source?: string | null): Channel {
  return source === 'whatsapp_gateway' ? 'whatsapp' : 'email'
}

interface ChannelLabels {
  badge: string
  unit: string
  unitPlural: string
  unitLower: string
  contact: string
  volumeTrend: string
  eventsHeading: string
  hasDomains: boolean
  hasBounceClassification: boolean
  hasInfrastructure: boolean
}

const LABELS: Record<Channel, ChannelLabels> = {
  email: {
    badge: 'Email',
    unit: 'Email',
    unitPlural: 'Emails',
    unitLower: 'emails',
    contact: 'Email',
    volumeTrend: 'Email Volume Trend',
    eventsHeading: 'Email Events',
    hasDomains: true,
    hasBounceClassification: true,
    hasInfrastructure: true,
  },
  whatsapp: {
    badge: 'WhatsApp',
    unit: 'Message',
    unitPlural: 'Messages',
    unitLower: 'messages',
    contact: 'Phone Number',
    volumeTrend: 'Message Volume Trend',
    eventsHeading: 'WhatsApp Messages',
    hasDomains: false,
    hasBounceClassification: false,
    hasInfrastructure: false,
  },
}

export function channelLabels(source?: string | null): ChannelLabels {
  return LABELS[channelFromSource(source)]
}
