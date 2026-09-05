import { ExternalLink, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { ErrorPanel, LoadingPanel, PageHeader } from '../components/Common'
import { auditRepository } from '../lib/repository'
import type { Authority } from '../types'

export function AuthoritiesPage() {
  const [authorities, setAuthorities] = useState<Authority[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    auditRepository.listAuthorities()
      .then(setAuthorities)
      .catch((value: Error) => setError(value.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => authorities.filter((authority) => {
    const haystack = `${authority.case_name} ${authority.citation} ${authority.passages.flatMap((passage) => passage.supported_propositions).join(' ')}`
    return haystack.toLowerCase().includes(search.toLowerCase())
  }), [authorities, search])

  return (
    <section className="page">
      <PageHeader
        eyebrow="Pilot corpus"
        title="Authority inventory"
        description="Every verdict traces to an immutable, proposition-annotated passage in this bounded corpus."
      />
      <div className="corpus-notice"><strong>Legal-research checkpoint.</strong> The included extracts were checked against linked official judgments; the team should confirm paragraph text, proposition labels, and limitations before the pitch.</div>
      <div className="panel">
        <div className="panel-toolbar">
          <div><p className="eyebrow">Corpus version 2026.09-pilot.1</p><h2>{authorities.length} selected decisions</h2></div>
          <label className="search-field"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search citation or proposition" /></label>
        </div>
        {loading && <LoadingPanel label="Loading authorities" />}
        {error && <ErrorPanel message={error} />}
        <div className="authority-list">
          {filtered.map((authority) => (
            <article className="authority-card" key={authority.id}>
              <div className="authority-title">
                <div><span>{authority.citation}</span><h3>{authority.case_name}</h3><p>{authority.court} · {new Date(authority.decision_date).getFullYear()}</p></div>
                <a href={authority.official_url} target="_blank" rel="noreferrer">Official source <ExternalLink size={13} /></a>
              </div>
              <div className="passage-grid">
                {authority.passages.map((passage) => (
                  <div className="passage-card" key={passage.id}>
                    <strong>{passage.paragraph_label}</strong>
                    <p>{passage.text}</p>
                    <div className="tag-row">{passage.supported_propositions.map((item) => <span key={item}>{item.replaceAll('_', ' ')}</span>)}</div>
                    {passage.limitations.length > 0 && <small>Limit: {passage.limitations.join(' ')}</small>}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
