import { CheckCircle2, FileUp, RefreshCw, Save, Sparkles, TriangleAlert } from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import { ErrorPanel, LoadingPanel, PageHeader } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { Authority, CaseMapAnnotation, CaseMapDetail, PractitionerFeedback } from '../types'

export function CaseMapsPage() {
  const [authorities, setAuthorities] = useState<Authority[]>([])
  const [maps, setMaps] = useState<CaseMapDetail[]>([])
  const [feedback, setFeedback] = useState<PractitionerFeedback[]>([])
  const [selectedCitation, setSelectedCitation] = useState('')
  const [selected, setSelected] = useState<CaseMapDetail | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'maps' | 'feedback'>('maps')

  async function load() {
    try {
      const [authorityRows, mapRows, feedbackRows] = await Promise.all([
        auditRepository.listCaseMapSources(), auditRepository.listCaseMaps(), auditRepository.listFeedback(),
      ])
      setAuthorities(authorityRows)
      setMaps(mapRows)
      setFeedback(feedbackRows)
      setSelectedCitation((value) => value || authorityRows[0]?.citation || '')
      setSelected((value) => value ?? mapRows[0] ?? null)
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Review data could not be loaded.')
    }
  }

  useEffect(() => { void load() }, [])

  async function generate() {
    if (!selectedCitation) return
    setBusy(true); setError('')
    try {
      const created = await auditRepository.generateCaseMap(selectedCitation)
      setMaps((items) => [created, ...items])
      setSelected(created)
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Case Map generation failed.')
    } finally { setBusy(false) }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const file = data.get('file')
    const citation = String(data.get('citation') || '')
    if (!(file instanceof File) || !citation) return
    setBusy(true); setError('')
    try {
      const created = await auditRepository.importCaseMapPdf(file, citation, String(data.get('url') || '') || undefined)
      setMaps((items) => [created, ...items]); setSelected(created); event.currentTarget.reset()
    } catch (value) {
      setError(value instanceof Error ? value.message : 'PDF import failed.')
    } finally { setBusy(false) }
  }

  async function saveAnnotation(annotation: CaseMapAnnotation) {
    if (!selected) return
    setBusy(true); setError('')
    try {
      const updated = await auditRepository.reviseCaseMap(selected.public_id, annotation.id, annotation)
      replace(updated)
    } catch (value) {
      setError(value instanceof Error ? value.message : 'Annotation could not be saved.')
    } finally { setBusy(false) }
  }

  async function approve() {
    if (!selected) return
    setBusy(true); setError('')
    try { replace(await auditRepository.approveCaseMap(selected.public_id)) }
    catch (value) { setError(value instanceof Error ? value.message : 'Approval failed.') }
    finally { setBusy(false) }
  }

  function replace(updated: CaseMapDetail) {
    setSelected(updated)
    setMaps((items) => items.some((item) => item.public_id === updated.public_id)
      ? items.map((item) => item.public_id === updated.public_id ? updated : item)
      : [updated, ...items])
  }

  return (
    <section className="page">
      <PageHeader eyebrow="Human review layer" title="Case Map workbench" description="Gemini proposes paragraph-anchored structure. Deterministic validation and a lawyer approval gate control runtime use." />
      <div className="tab-row">
        <button className={tab === 'maps' ? 'tab active' : 'tab'} onClick={() => setTab('maps')}>Case Maps</button>
        <button className={tab === 'feedback' ? 'tab active' : 'tab'} onClick={() => setTab('feedback')}>Practitioner feedback · {feedback.length}</button>
      </div>
      {error && <ErrorPanel message={error} />}
      {tab === 'feedback' ? (
        <div className="panel review-list">
          {feedback.length === 0 ? <p className="empty-copy">No practitioner flags are awaiting review.</p> : feedback.map((item) => (
            <article key={item.public_id}><span className="status-pill warning">{item.status.replace('_', ' ')}</span><h3>{item.category.replaceAll('_', ' ')}</h3><p>{item.explanation}</p><small>Claim {item.claim_order} · {new Date(item.created_at).toLocaleString()}</small></article>
          ))}
        </div>
      ) : (
        <>
          <div className="case-map-actions">
            <div className="panel generate-card">
              <p className="eyebrow">Official snapshot</p><h2>Generate anchored draft</h2>
              <select value={selectedCitation} onChange={(event) => setSelectedCitation(event.target.value)}>
                {authorities.map((authority) => <option key={authority.id} value={authority.citation}>{authority.citation} · {authority.case_name}</option>)}
              </select>
              <button className="button primary" disabled={busy || !selectedCitation} onClick={generate}>{busy ? <RefreshCw size={16} /> : <Sparkles size={16} />}Generate Case Map</button>
            </div>
            <form className="panel generate-card" onSubmit={upload}>
              <p className="eyebrow">Secondary intake</p><h2>Import text PDF</h2>
              <input name="file" type="file" accept="application/pdf" required />
              <input name="citation" placeholder="Expected citation, e.g. [2024] SGHC 94" required />
              <input name="url" type="url" placeholder="Optional official source URL" />
              <button className="button secondary" disabled={busy} type="submit"><FileUp size={16} />Create user-supplied draft</button>
              <small>The binary is discarded. Scans, encrypted files and files over 15 MB are rejected.</small>
            </form>
          </div>
          <div className="case-map-grid">
            <aside className="panel map-list">
              <div className="panel-heading-inline"><div><p className="eyebrow">Review queue</p><h2>{maps.length} maps</h2></div></div>
              {maps.map((item) => <button key={item.public_id} className={selected?.public_id === item.public_id ? 'map-row active' : 'map-row'} onClick={() => setSelected(item)}><strong>{item.citation}</strong><span>{item.case_name}</span><small>{item.status} · v{item.version}</small></button>)}
              {maps.length === 0 && <p className="empty-copy">Generate a map from an active authority to begin.</p>}
            </aside>
            {selected ? <MapEditor map={selected} busy={busy} onChange={replace} onSave={saveAnnotation} onApprove={approve} /> : <div className="panel"><LoadingPanel label="Select or generate a Case Map" /></div>}
          </div>
        </>
      )}
    </section>
  )
}

function MapEditor({ map, busy, onChange, onSave, onApprove }: { map: CaseMapDetail; busy: boolean; onChange: (map: CaseMapDetail) => void; onSave: (annotation: CaseMapAnnotation) => void; onApprove: () => void }) {
  function update(id: string, field: keyof CaseMapAnnotation, value: unknown) {
    onChange({ ...map, annotations: map.annotations.map((item) => item.id === id ? { ...item, [field]: value } : item) })
  }
  return (
    <div className="map-editor">
      <div className="panel map-summary">
        <div><p className="eyebrow">{map.source_provenance.replace('_', ' ')}</p><h2>{map.case_name}</h2><p>{map.citation} · schema {map.schema_version} · {map.model}</p></div>
        <button className="button primary" disabled={busy || map.status === 'stale' || map.validation_errors.length > 0} onClick={onApprove}><CheckCircle2 size={16} />Approve revision</button>
      </div>
      {map.status === 'stale' && <div className="offline-banner"><TriangleAlert size={18} /><div><strong>Stale source hash</strong><p>Regenerate this map from the current official snapshot before approval.</p></div></div>}
      {map.annotations.map((annotation) => (
        <article className="panel annotation-card" key={annotation.id}>
          <div className="annotation-grid">
            <label>Authority role<select value={annotation.annotation_type} onChange={(event) => update(annotation.id, 'annotation_type', event.target.value)}>{['holding', 'ratio_candidate', 'obiter_candidate', 'party_submission', 'factual_finding', 'procedural_history', 'disposition'].map((role) => <option key={role}>{role}</option>)}</select></label>
            <label>Modality<select value={annotation.modality} onChange={(event) => update(annotation.id, 'modality', event.target.value)}>{['mandatory', 'qualified', 'permissive', 'descriptive'].map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Paragraphs<input value={annotation.paragraph_labels.join(', ')} onChange={(event) => update(annotation.id, 'paragraph_labels', event.target.value.split(',').map((value) => value.trim()))} /></label>
          </div>
          <label>Structured statement<textarea value={annotation.statement} onChange={(event) => update(annotation.id, 'statement', event.target.value)} /></label>
          <label>Exact supporting quotation<textarea value={annotation.supporting_quote} onChange={(event) => update(annotation.id, 'supporting_quote', event.target.value)} /></label>
          {annotation.validation_messages.map((message) => <p className="validation-error" key={message}>{message}</p>)}
          <div className="annotation-footer"><span>{Math.round(annotation.model_confidence * 100)}% model confidence · {annotation.validation_status}</span><button className="button secondary" disabled={busy} onClick={() => onSave(annotation)}><Save size={15} />Validate & save</button></div>
        </article>
      ))}
      <details className="panel source-paragraphs"><summary>View {map.source_paragraphs.length} immutable source paragraphs</summary>{map.source_paragraphs.map((passage) => <blockquote key={passage.id}><strong>{passage.paragraph_label}</strong> {passage.text}</blockquote>)}</details>
    </div>
  )
}
