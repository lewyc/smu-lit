import type {
  AuditDetail,
  AuditFilters,
  AuditRepository,
  AuditSubmission,
  AuditSummary,
  Authority,
  BenchmarkResult,
} from '../types'
import { DEMO_ANSWER, savedDemoResult } from './demo'
import { accessToken, apiUrl, dataMode } from './supabase'

const CACHE_KEY = 'proofmark:last-audit'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await accessToken()
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${apiUrl}${path}`, { ...init, headers })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

function store(audit: AuditDetail) {
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(audit))
  }
}

function cached(publicId?: string): AuditDetail | null {
  if (typeof sessionStorage === 'undefined') return null
  const raw = sessionStorage.getItem(CACHE_KEY)
  if (!raw) return null
  const audit = JSON.parse(raw) as AuditDetail
  return !publicId || audit.public_id === publicId ? audit : null
}

export class ApiAuditRepository implements AuditRepository {
  async listAudits(filters?: AuditFilters): Promise<AuditSummary[]> {
    try {
      const audits = await request<AuditSummary[]>('/api/v1/audits')
      return audits.filter((audit) => {
        const matchesSearch = !filters?.search
          || audit.input_preview.toLowerCase().includes(filters.search.toLowerCase())
        const matchesVerdict = !filters?.verdict
          || (audit.summary_counts[filters.verdict] ?? 0) > 0
        return matchesSearch && matchesVerdict
      })
    } catch (error) {
      if (dataMode === 'supabase') throw error
      return [cached() ?? savedDemoResult]
    }
  }

  async getAudit(publicId: string): Promise<AuditDetail> {
    const local = cached(publicId)
    if (local) return local
    try {
      const audit = await request<AuditDetail>(`/api/v1/audits/${publicId}`)
      store(audit)
      return audit
    } catch (error) {
      if (dataMode === 'supabase' || publicId !== savedDemoResult.public_id) throw error
      return savedDemoResult
    }
  }

  async submitAudit(input: AuditSubmission): Promise<AuditDetail> {
    try {
      const audit = await request<AuditDetail>('/api/v1/audits', {
        method: 'POST',
        body: JSON.stringify(input),
      })
      store(audit)
      return audit
    } catch (error) {
      if (dataMode === 'supabase' || input.answer.trim() !== DEMO_ANSWER.trim()) throw error
      store(savedDemoResult)
      return savedDemoResult
    }
  }

  runBenchmark(): Promise<BenchmarkResult> {
    return request('/api/v1/benchmarks/run', { method: 'POST' })
  }

  listAuthorities(): Promise<Authority[]> {
    return request('/api/v1/authorities')
  }

  async loadDemoAnswer(): Promise<string> {
    try {
      const payload = await request<{ answer: string }>('/api/v1/demo-answer')
      return payload.answer
    } catch {
      return DEMO_ANSWER
    }
  }
}

export const auditRepository = new ApiAuditRepository()
