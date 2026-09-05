import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'

const AssurancePage = lazy(() => import('./pages/AssurancePage').then((module) => ({ default: module.AssurancePage })))
const AuditDetailPage = lazy(() => import('./pages/AuditDetailPage').then((module) => ({ default: module.AuditDetailPage })))
const AuditsPage = lazy(() => import('./pages/AuditsPage').then((module) => ({ default: module.AuditsPage })))
const AuthoritiesPage = lazy(() => import('./pages/AuthoritiesPage').then((module) => ({ default: module.AuthoritiesPage })))
const BenchmarkPage = lazy(() => import('./pages/BenchmarkPage').then((module) => ({ default: module.BenchmarkPage })))
const CaseMapsPage = lazy(() => import('./pages/CaseMapsPage').then((module) => ({ default: module.CaseMapsPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })))
const NewAuditPage = lazy(() => import('./pages/NewAuditPage').then((module) => ({ default: module.NewAuditPage })))

export default function App() {
  return (
    <Suspense fallback={<div className="route-loading"><span className="spinner" />Loading ProofMark…</div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AppLayout />}>
          <Route path="/audits" element={<AuditsPage />} />
          <Route path="/audits/new" element={<NewAuditPage />} />
          <Route path="/audits/:id" element={<AuditDetailPage />} />
          <Route path="/authorities" element={<AuthoritiesPage />} />
          <Route path="/case-maps" element={<CaseMapsPage />} />
          <Route path="/benchmark" element={<BenchmarkPage />} />
          <Route path="/assurance" element={<AssurancePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/audits" replace />} />
      </Routes>
    </Suspense>
  )
}
