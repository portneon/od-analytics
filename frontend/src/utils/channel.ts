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
  domainLabel: string
  domainLabelPlural: string
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
    domainLabel: 'Domain',
    domainLabelPlural: 'Domains',
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
    // The gateway's "Sender" is always the same gateway number, so it
    // carries no org identity -- the WhatsApp adapter extracts the actual
    // sending institute from the message body and rides it in on the same
    // Domain dimension/metrics the email channel uses for recipient
    // domains. Same data plumbing, different real-world meaning, so it's
    // relabeled here rather than given a parallel dimension.
    hasDomains: true,
    domainLabel: 'Institute',
    domainLabelPlural: 'Institutes',
    hasBounceClassification: false,
    hasInfrastructure: false,
  },
}

export function channelLabels(source?: string | null): ChannelLabels {
  return LABELS[channelFromSource(source)]
}
