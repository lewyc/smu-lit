import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

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
})
