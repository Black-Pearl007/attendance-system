import { useEffect, useState } from 'react'
import { api, fmt } from '../api'
import { useAuth } from '../auth.jsx'

export default function Privacy() {
  const { user } = useAuth()
  const [policy, setPolicy] = useState(null)
  const [audit, setAudit] = useState([])
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/privacy/policy').then(setPolicy).catch((e) => setError(e.message))
    if (user.role === 'admin') api.get('/privacy/audit?limit=50').then(setAudit).catch(() => {})
  }, [user.role])

  const purge = async () => {
    try { const r = await api.post('/privacy/purge-expired', {}); setMsg(`Deleted ${r.deleted} expired face template(s).`) } catch (e) { setError(e.message) }
  }

  return (
    <>
      <h1>Privacy &amp; data protection</h1>
      {error && <div className="notice bad">{error}</div>}
      {policy && <section className="card"><pre className="policy">{policy.policy}</pre></section>}
      {user.role === 'admin' && (
        <>
          <section className="card">
            <h2>Retention</h2>
            <p className="muted">Face templates older than {policy?.retention_days ?? '…'} days are removed when you run the purge.</p>
            <button className="btn" onClick={purge}>Purge expired templates</button>
            {msg && <p>{msg}</p>}
          </section>
          <section className="card">
            <h2>Audit log (latest 50)</h2>
            <table>
              <thead><tr><th>When</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead>
              <tbody>{audit.map((a) => <tr key={a.id}><td>{fmt(a.created_at)}</td><td>{a.action}</td><td>{a.target}</td><td>{a.detail}</td></tr>)}</tbody>
            </table>
          </section>
        </>
      )}
    </>
  )
}
