import type {
  AuditDetail,
  AuditFilters,
  AuditRepository,
  AuditSubmission,
  AuditSummary,
  Authority,
  BenchmarkResult,
  CorpusMetadata,
  RefreshRun,
  CaseMapAnnotation,
  CaseMapDetail,
  FeedbackSubmission,
  PractitionerFeedback,
  HumanReviewDecision,
  HumanReviewItem,
  VeritasDemoSuite,
  VeritasOperatingConfig,
} from '../types'
import { DEMO_ANSWER, savedDemoResult } from './demo'
import { accessToken, apiUrl, dataMode } from './supabase'

const CACHE_KEY = 'proofmark:last-audit'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await accessToken()
  const headers = new Headers(init?.headers)
  if (!(init?.body instanceof FormData)) headers.set('Content-Type', 'application/json')
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

  async reAudit(publicId: string): Promise<AuditDetail> {
    const audit = await request<AuditDetail>('/api/v1/audits/' + publicId + '/re-audit', { method: 'POST' })
    store(audit)
    return audit
  }

  async deleteAudit(publicId: string): Promise<void> {
    const token = await accessToken()
    const headers = new Headers()
    if (token) headers.set('Authorization', 'Bearer ' + token)
    const response = await fetch(apiUrl + '/api/v1/audits/' + publicId, { method: 'DELETE', headers })
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail ?? 'Audit could not be deleted')
    }
    if (cached(publicId) && typeof sessionStorage !== 'undefined') sessionStorage.removeItem(CACHE_KEY)
  }

  runBenchmark(): Promise<BenchmarkResult> {
    return request('/api/v1/benchmarks/run', { method: 'POST' })
  }

  getVeritasConfig(): Promise<VeritasOperatingConfig> {
    return request('/api/v1/veritas/config')
  }

  runVeritasDemos(): Promise<VeritasDemoSuite> {
    return request('/api/v1/veritas/demos/run', { method: 'POST' })
  }

  listHumanReviews(): Promise<HumanReviewItem[]> {
    return request('/api/v1/veritas/reviews')
  }

  submitHumanDecision(
    publicId: string,
    input: Omit<HumanReviewDecision, 'decided_at' | 'dissent'> & { dissent?: string },
  ): Promise<HumanReviewItem> {
    return request('/api/v1/veritas/reviews/' + publicId + '/decisions', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  listAuthorities(): Promise<Authority[]> {
    return request('/api/v1/authorities')
  }

  listCaseMapSources(): Promise<Authority[]> {
    return request('/api/v1/case-map-sources')
  }

  async getCorpus(): Promise<CorpusMetadata> {
    const corpora = await request<CorpusMetadata[]>('/api/v1/corpora')
    if (!corpora[0]) throw new Error('No active corpus metadata is available')
    return corpora[0]
  }

  startCorpusRefresh(): Promise<RefreshRun> {
    return request('/api/v1/corpora/refresh', {
      method: 'POST',
      body: JSON.stringify({ limit: 25 }),
    })
  }

  getLatestCorpusRefresh(): Promise<RefreshRun | null> {
    return request('/api/v1/corpora/refreshes/latest')
  }

  async loadDemoAnswer(): Promise<string> {
    try {
      const payload = await request<{ answer: string }>('/api/v1/demo-answer')
      return payload.answer
    } catch {
      return DEMO_ANSWER
    }
  }

  listCaseMaps(): Promise<CaseMapDetail[]> {
    return request('/api/v1/case-maps')
  }

  generateCaseMap(citation: string): Promise<CaseMapDetail> {
    return request('/api/v1/case-maps/generate', { method: 'POST', body: JSON.stringify({ citation }) })
  }

  importCaseMapPdf(file: File, expectedCitation: string, officialUrl?: string): Promise<CaseMapDetail> {
    const body = new FormData()
    body.set('file', file)
    body.set('expected_citation', expectedCitation)
    if (officialUrl) body.set('official_url', officialUrl)
    return request('/api/v1/case-maps/import-pdf', { method: 'POST', body })
  }

  reviseCaseMap(publicId: string, annotationId: string, revision: Partial<CaseMapAnnotation>): Promise<CaseMapDetail> {
    return request(`/api/v1/case-maps/${publicId}/annotations/${annotationId}`, {
      method: 'PATCH', body: JSON.stringify(revision),
    })
  }

  approveCaseMap(publicId: string): Promise<CaseMapDetail> {
    return request(`/api/v1/case-maps/${publicId}/approve`, { method: 'POST' })
  }

  submitFeedback(input: FeedbackSubmission): Promise<PractitionerFeedback> {
    return request('/api/v1/feedback', { method: 'POST', body: JSON.stringify(input) })
  }

  listFeedback(): Promise<PractitionerFeedback[]> {
    return request('/api/v1/feedback')
  }
}

export const auditRepository = new ApiAuditRepository()
