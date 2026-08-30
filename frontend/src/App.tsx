import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/layouts/AppShell'
import { DatasetLayout } from '@/layouts/DatasetLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { DatasetsPage } from '@/pages/DatasetsPage'
import { OverviewTab } from '@/pages/dataset/OverviewTab'
import { AnalyticsTab } from '@/pages/dataset/AnalyticsTab'
import { RecipientsTab } from '@/pages/dataset/RecipientsTab'
import { RecipientDetailPage } from '@/pages/dataset/RecipientDetailPage'
import { DomainsTab } from '@/pages/dataset/DomainsTab'
import { DomainDetailPage } from '@/pages/dataset/DomainDetailPage'
import { SubjectsTab } from '@/pages/dataset/SubjectsTab'
import { SendersTab } from '@/pages/dataset/SendersTab'
import { BouncesTab } from '@/pages/dataset/BouncesTab'
import { InfrastructureTab } from '@/pages/dataset/InfrastructureTab'
import { AnomaliesTab } from '@/pages/dataset/AnomaliesTab'
import { EventsTab } from '@/pages/dataset/EventsTab'
import { AskTab } from '@/pages/dataset/AskTab'
import { ReportsTab } from '@/pages/dataset/ReportsTab'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/datasets" element={<DatasetsPage />} />

        <Route path="/datasets/:datasetId" element={<DatasetLayout />}>
          <Route index element={<OverviewTab />} />
          <Route path="analytics" element={<AnalyticsTab />} />
          <Route path="recipients" element={<RecipientsTab />} />
          <Route path="recipients/:recipientId" element={<RecipientDetailPage />} />
          <Route path="domains" element={<DomainsTab />} />
          <Route path="domains/:domainId" element={<DomainDetailPage />} />
          <Route path="subjects" element={<SubjectsTab />} />
          <Route path="senders" element={<SendersTab />} />
          <Route path="bounces" element={<BouncesTab />} />
          <Route path="infrastructure" element={<InfrastructureTab />} />
          <Route path="anomalies" element={<AnomaliesTab />} />
          <Route path="events" element={<EventsTab />} />
          <Route path="ask" element={<AskTab />} />
          <Route path="reports" element={<ReportsTab />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
