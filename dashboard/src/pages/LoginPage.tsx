import { Scale } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getSupabase, dataMode } from '../lib/supabase'

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const supabase = getSupabase()
    if (!supabase) {
      setError('Supabase mode or publishable credentials are not configured.')
      return
    }
    setLoading(true)
    const { error: authError } = await supabase.auth.signInWithPassword({ email, password })
    setLoading(false)
    if (authError) return setError(authError.message)
    navigate('/audits')
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand"><span><Scale size={22} /></span><strong>VERITAS</strong></div>
        <p className="eyebrow">Connected mode</p>
        <h1>Sign in to your organisation</h1>
        <p>Use the demonstration account created in Supabase Auth.</p>
        <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
        {error && <div className="form-error">{error}</div>}
        <button className="button primary" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button>
        {dataMode === 'demo' && <Link to="/audits">Return to demo mode</Link>}
      </form>
    </main>
  )
}
