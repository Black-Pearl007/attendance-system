import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, fmt } from '../api'

export default function CourseDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [course, setCourse] = useState(null)
  const [enrolled, setEnrolled] = useState([])
  const [all, setAll] = useState([])
  const [sessions, setSessions] = useState([])
  const [picked, setPicked] = useState([])
  const [title, setTitle] = useState('')
  const [late, setLate] = useState(10)
  const [error, setError] = useState('')

  const load = async () => {
    try {
      const [courses, st, every, ss] = await Promise.all([
        api.get('/courses'), api.get(`/courses/${id}/students`), api.get('/students'), api.get(`/sessions?course_id=${id}`),
      ])
      setCourse(courses.find((c) => String(c.id) === id) || null)
      setEnrolled(st); setAll(every); setSessions(ss)
    } catch (e) { setError(e.message) }
  }
  useEffect(() => { load() }, [id])

  const act = async (fn) => { setError(''); try { await fn(); await load() } catch (e) { setError(e.message) } }
  const enrolledIds = new Set(enrolled.map((s) => s.id))
  const available = all.filter((s) => !enrolledIds.has(s.id))

  const startSession = async (e) => {
    e.preventDefault()
    try {
      const s = await api.post('/sessions', { course_id: Number(id), title, late_after_minutes: Number(late) })
      nav(`/sessions/${s.id}`)
    } catch (err) { setError(err.message) }
  }

  if (!course) return <>{error ? <div className="notice bad">{error}</div> : <p className="muted">Loading…</p>}</>

  return (
    <>
      <Link to="/courses" className="back">← Courses</Link>
      <h1>{course.code} <span className="muted">{course.name}</span></h1>
      {error && <div className="notice bad">{error}</div>}

      <form className="card inline-form" onSubmit={startSession}>
        <h2>Start a class session</h2>
        <div className="row">
          <label className="grow">Title<input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Lecture 5" required /></label>
          <label>Late after (min)<input type="number" min="0" max="240" value={late} onChange={(e) => setLate(e.target.value)} /></label>
        </div>
        <button className="btn primary">Start session</button>
      </form>

      <div className="grid-2">
        <section className="card">
          <h2>Enrolled students ({enrolled.length})</h2>
          <table>
            <tbody>
              {enrolled.length === 0 && <tr><td className="muted">Nobody enrolled yet.</td></tr>}
              {enrolled.map((s) => (
                <tr key={s.id}>
                  <td>{s.roll_no}</td><td>{s.name}</td>
                  <td>{s.face_count === 0 && <span className="badge warn">no face</span>}</td>
                  <td className="actions"><button className="btn sm ghost" onClick={() => act(() => api.del(`/courses/${id}/students/${s.id}`))}>Remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="card">
          <h2>Add students</h2>
          {available.length === 0 ? <p className="muted">All students are already in this course.</p> : (
            <>
              <div className="picklist">
                {available.map((s) => (
                  <label key={s.id} className="check">
                    <input type="checkbox" checked={picked.includes(s.id)}
                      onChange={(e) => setPicked(e.target.checked ? [...picked, s.id] : picked.filter((x) => x !== s.id))} />
                    <span>{s.roll_no} — {s.name}</span>
                  </label>
                ))}
              </div>
              <button className="btn" disabled={!picked.length}
                onClick={() => act(async () => { await api.post(`/courses/${id}/students`, { student_ids: picked }); setPicked([]) })}>
                Add {picked.length || ''} selected
              </button>
            </>
          )}
        </section>
      </div>

      <section className="card">
        <h2>Sessions</h2>
        <table>
          <thead><tr><th>Title</th><th>Started</th><th>Status</th><th /></tr></thead>
          <tbody>
            {sessions.length === 0 && <tr><td colSpan="4" className="muted">No sessions yet.</td></tr>}
            {sessions.map((s) => (
              <tr key={s.id}>
                <td>{s.title}</td><td>{fmt(s.starts_at)}</td>
                <td><span className={`badge ${s.status === 'open' ? 'good' : ''}`}>{s.status}</span></td>
                <td className="actions"><Link className="btn sm" to={`/sessions/${s.id}`}>{s.status === 'open' ? 'Open' : 'View'}</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
