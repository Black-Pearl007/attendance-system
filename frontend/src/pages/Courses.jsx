import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function Courses() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState({ code: '', name: '' })
  const [error, setError] = useState('')
  const load = () => api.get('/courses').then(setRows).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const add = async (e) => {
    e.preventDefault()
    setError('')
    try { await api.post('/courses', form); setForm({ code: '', name: '' }); await load() } catch (err) { setError(err.message) }
  }

  return (
    <>
      <h1>Courses</h1>
      {error && <div className="notice bad">{error}</div>}
      <form className="card inline-form" onSubmit={add}>
        <h2>New course</h2>
        <div className="row">
          <label>Code<input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required /></label>
          <label className="grow">Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
        </div>
        <button className="btn primary">Create course</button>
      </form>
      <section className="cards">
        {rows.length === 0 && <p className="muted">No courses yet.</p>}
        {rows.map((c) => (
          <Link key={c.id} to={`/courses/${c.id}`} className="card course">
            <b>{c.code}</b>
            <span>{c.name}</span>
            <small className="muted">{c.student_count} students</small>
          </Link>
        ))}
      </section>
    </>
  )
}
