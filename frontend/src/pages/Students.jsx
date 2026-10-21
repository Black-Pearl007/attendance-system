import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth.jsx'

export default function Students() {
  const { user } = useAuth()
  const [rows, setRows] = useState([])
  const [form, setForm] = useState({ roll_no: '', name: '', email: '', consent: false })
  const [error, setError] = useState('')

  const load = () => api.get('/students').then(setRows).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const act = async (fn) => { setError(''); try { await fn(); await load() } catch (e) { setError(e.message) } }

  const add = (e) => {
    e.preventDefault()
    act(async () => {
      await api.post('/students', { ...form, email: form.email || null })
      setForm({ roll_no: '', name: '', email: '', consent: false })
    })
  }

  return (
    <>
      <h1>Students</h1>
      {error && <div className="notice bad">{error}</div>}

      <form className="card inline-form" onSubmit={add}>
        <h2>Add student</h2>
        <div className="row">
          <label>Roll no<input value={form.roll_no} onChange={(e) => setForm({ ...form, roll_no: e.target.value })} required /></label>
          <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
          <label>Email (optional)<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        </div>
        <label className="check">
          <input type="checkbox" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} />
          <span>The student has given informed, voluntary consent to biometric (face template) processing for attendance. Without consent, no face can be enrolled — use manual roll-call instead.</span>
        </label>
        <button className="btn primary">Add student</button>
      </form>

      <section className="card">
        <table>
          <thead><tr><th>Roll no</th><th>Name</th><th>Consent</th><th>Face templates</th><th /></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan="5" className="muted">No students yet.</td></tr>}
            {rows.map((s) => (
              <tr key={s.id}>
                <td>{s.roll_no}</td>
                <td>{s.name}</td>
                <td>{s.consent_given ? <span className="badge good">Given</span> : <span className="badge warn">None</span>}</td>
                <td>{s.face_count}</td>
                <td className="actions">
                  {s.consent_given && <Link className="btn sm" to={`/students/${s.id}/enroll`}>{s.face_count ? 'Add faces' : 'Enrol face'}</Link>}
                  {!s.consent_given && <button className="btn sm" onClick={() => act(() => api.post(`/students/${s.id}/consent`, { given: true }))}>Record consent</button>}
                  {s.consent_given && <button className="btn sm ghost" title="Withdrawing consent also erases the face templates"
                    onClick={() => confirm(`Withdraw consent for ${s.name}? Their face templates will be deleted.`) && act(() => api.post(`/students/${s.id}/consent`, { given: false }))}>Withdraw consent</button>}
                  {s.face_count > 0 && <button className="btn sm ghost"
                    onClick={() => confirm(`Delete all face templates of ${s.name}?`) && act(() => api.del(`/students/${s.id}/biometrics`))}>Delete faces</button>}
                  {user.role === 'admin' && <button className="btn sm danger"
                    onClick={() => confirm(`Delete ${s.name} and all their records?`) && act(() => api.del(`/students/${s.id}`))}>Delete</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
