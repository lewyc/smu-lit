import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, vi } from 'vitest'
import App from './App'
import { auditRepository } from './lib/repository'

afterEach(() => vi.restoreAllMocks())

describe('ProofMark dashboard', () => {
  it('keeps the pilot limitations visible on the assurance route', async () => {
    render(
      <MemoryRouter initialEntries={['/assurance']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Help lawyers triage/i)).toBeInTheDocument()
    expect(screen.getByText(/Pilot evaluation tool/i)).toBeInTheDocument()
    expect(screen.getByText(/Production architecture/i)).toBeInTheDocument()
  })

  it('loads the new audit form in demo mode without Supabase credentials', async () => {
    render(
      <MemoryRouter initialEntries={['/audits/new']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('textbox', { name: /AI-generated legal answer/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Load demonstration answer/i })).toBeInTheDocument()
  })

  it('reveals contextual inputs only when full mode is selected', async () => {
    render(
      <MemoryRouter initialEntries={['/audits/new']}>
        <App />
      </MemoryRouter>,
    )
    const auditDepth = await screen.findByLabelText(/Audit depth/i)
    expect(screen.queryByPlaceholderText(/What question was the AI asked/i)).not.toBeInTheDocument()
    fireEvent.change(auditDepth, { target: { value: 'full' } })
    expect(screen.getByPlaceholderText(/What question was the AI asked/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Duration, territory/i)).toBeInTheDocument()
  })

  it('exposes the Case Map human-review workbench', async () => {
    vi.spyOn(auditRepository, 'listCaseMapSources').mockResolvedValue([])
    vi.spyOn(auditRepository, 'listCaseMaps').mockResolvedValue([])
    vi.spyOn(auditRepository, 'listFeedback').mockResolvedValue([])
    render(
      <MemoryRouter initialEntries={['/case-maps']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Case Map workbench/i)).toBeInTheDocument()
    expect(screen.getByText(/Generate anchored draft/i)).toBeInTheDocument()
    expect(screen.getByText(/Practitioner feedback/i)).toBeInTheDocument()
    expect(await screen.findByText(/0 maps/i)).toBeInTheDocument()
  })
})
