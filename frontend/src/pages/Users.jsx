import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Users() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'teacher' })
  const [error, setError] = useState('')
  const load = () => api.get('/auth/users').then(setRows).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const add = async (e) => {
    e.preventDefault()
    setError('')
    try { await api.post('/auth/users', form); setForm({ name: '', email: '', password: '', role: 'teacher' }); await load() } catch (err) { setError(err.message) }
  }

  return (
    <>
      <h1>Users</h1>
      {error && <div className="notice bad">{error}</div>}
      <form className="card inline-form" onSubmit={add}>
        <h2>Add teacher / admin</h2>
        <div className="row">
          <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
          <label>Email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></label>
          <label>Password (8+ chars)<input type="password" minLength="8" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required /></label>
          <label>Role
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="teacher">Teacher</option><option value="admin">Admin</option>
            </select>
          </label>
        </div>
        <button className="btn primary">Create user</button>
      </form>
      <section className="card">
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th></tr></thead>
          <tbody>{rows.map((u) => <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td><span className="badge">{u.role}</span></td></tr>)}</tbody>
        </table>
      </section>
    </>
  )
}
