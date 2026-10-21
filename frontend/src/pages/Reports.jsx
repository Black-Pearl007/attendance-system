import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'

const colour = (p) => (p == null ? '#94a3b8' : p >= 75 ? '#0f766e' : p >= 50 ? '#d97706' : '#b91c1c')

export default function Reports() {
  const [courses, setCourses] = useState([])
  const [courseId, setCourseId] = useState('')
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { api.get('/courses').then(setCourses).catch((e) => setError(e.message)) }, [])
  useEffect(() => {
    if (!courseId) { setReport(null); return }
    api.get(`/reports/course/${courseId}`).then(setReport).catch((e) => setError(e.message))
  }, [courseId])

  const dl = (fmt) => {
    const code = courses.find((c) => String(c.id) === courseId)?.code || 'course'
    api.download(`/reports/course/${courseId}/export?format=${fmt}`, `${code}_summary.${fmt}`).catch((e) => setError(e.message))
  }

  return (
    <>
      <h1>Reports</h1>
      {error && <div className="notice bad">{error}</div>}
      <div className="card inline-form">
        <label>Course
          <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
            <option value="">Select a course…</option>
            {courses.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
          </select>
        </label>
      </div>

      {report && (
        <>
          <p className="muted">Percentages cover the {report.closed_sessions} closed session(s). Late counts as attended.</p>
          {report.closed_sessions === 0 ? <div className="notice">Close at least one session to see statistics.</div> : (
            <>
              <section className="card">
                <h2>Attendance by student</h2>
                <ResponsiveContainer width="100%" height={Math.max(220, report.students.length * 34)}>
                  <BarChart data={report.students} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                    <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v) => (v == null ? 'n/a' : `${v}%`)} />
                    <Bar dataKey="percent" radius={[0, 4, 4, 0]}>
                      {report.students.map((s) => <Cell key={s.student_id} fill={colour(s.percent)} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </section>
              <section className="card">
                <h2>Attendance by session</h2>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={report.sessions}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="title" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v) => `${v}%`} />
                    <Bar dataKey="percent" fill="#0f766e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </section>
            </>
          )}
          <section className="card">
            <div className="card-head">
              <h2>Summary table</h2>
              <div className="toolbar">
                <button className="btn sm" onClick={() => dl('csv')}>Export CSV</button>
                <button className="btn sm" onClick={() => dl('xlsx')}>Export Excel</button>
              </div>
            </div>
            <table>
              <thead><tr><th>Roll no</th><th>Name</th><th>Present</th><th>Late</th><th>Absent</th><th>Attendance</th></tr></thead>
              <tbody>
                {report.students.map((s) => (
                  <tr key={s.student_id}>
                    <td>{s.roll_no}</td><td>{s.name}</td><td>{s.present}</td><td>{s.late}</td><td>{s.absent}</td>
                    <td><b style={{ color: colour(s.percent) }}>{s.percent == null ? '—' : `${s.percent}%`}</b></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </>
  )
}
