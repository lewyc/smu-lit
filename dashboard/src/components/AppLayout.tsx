import {
  BarChart3,
  BookOpenText,
  FileCheck2,
  Menu,
  Plus,
  Scale,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { dataMode } from '../lib/supabase'

const navigation = [
  { to: '/audits', label: 'Audit worklist', icon: FileCheck2 },
  { to: '/audits/new', label: 'New audit', icon: Plus },
  { to: '/authorities', label: 'Authorities', icon: BookOpenText },
  { to: '/benchmark', label: 'Benchmark', icon: BarChart3 },
  { to: '/assurance', label: 'Assurance', icon: ShieldCheck },
]

export function AppLayout() {
  const [open, setOpen] = useState(false)
  return (
    <div className="app-shell">
      <button className="mobile-menu" onClick={() => setOpen(true)} aria-label="Open navigation">
        <Menu size={20} />
      </button>
      {open && <button className="drawer-scrim" onClick={() => setOpen(false)} aria-label="Close navigation" />}
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="brand-row">
          <span className="brand-mark"><Scale size={19} /></span>
          <div><strong>ProofMark</strong><small>Legal AI assurance</small></div>
          <button className="drawer-close" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="pilot-chip">Pilot · {dataMode} mode</div>
        <nav>
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}
            >
              <Icon size={17} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={17} />
          <p><strong>Human accountable</strong><br />Flagged claims require lawyer review.</p>
        </div>
      </aside>
      <main className="main-content">
        <div className="scope-banner">
          Pilot evaluation tool · Singapore employment restraints only · Not legal advice
        </div>
        <Outlet />
      </main>
    </div>
  )
}
