import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'

export default function Dashboard() {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.get('/reports/dashboard').then(setD).catch((e) => setError(e.message)) }, [])

  if (error) return <div className="notice bad">{error}</div>
  if (!d) return <p className="muted">Loading…</p>

  return (
    <>
      <h1>Dashboard</h1>
      <div className="stats">
        <div className="stat"><b>{d.students}</b><span>Students</span></div>
        <div className="stat"><b>{d.courses}</b><span>Courses</span></div>
        <div className="stat"><b>{d.open_sessions}</b><span>Open sessions</span></div>
      </div>
      <section className="card">
        <h2>Attendance, last 14 days</h2>
        {d.trend.length === 0 ? (
          <p className="muted">No attendance recorded yet. Create a course, enrol students and start a session.</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={d.trend}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="present" stackId="a" fill="#0f766e" />
              <Bar dataKey="late" stackId="a" fill="#d97706" />
              <Bar dataKey="absent" stackId="a" fill="#b91c1c" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>
    </>
  )
}
