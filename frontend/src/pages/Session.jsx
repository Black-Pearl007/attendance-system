import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fmt } from '../api'
import CameraView from '../components/CameraView.jsx'
import { sleep, useWebcam } from '../useWebcam'

const FRAME_INTERVAL_MS = 350

export default function Session() {
  const { id } = useParams()
  const cam = useWebcam()
  const [detail, setDetail] = useState(null)
  const [faces, setFaces] = useState([])
  const [scanning, setScanning] = useState(false)
  const [toasts, setToasts] = useState([])
  const [error, setError] = useState('')
  const running = useRef(false)

  const load = useCallback(() => api.get(`/sessions/${id}`).then(setDetail).catch((e) => setError(e.message)), [id])
  useEffect(() => { load() }, [load])

  const toast = (text) => {
    const key = Math.random()
    setToasts((t) => [...t, { key, text }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.key !== key)), 4000)
  }

  const stopScan = useCallback(() => { running.current = false; setScanning(false); setFaces([]) }, [])

  const startScan = async () => {
    if (cam.state !== 'on' && !(await cam.start())) return
    setError('')
    await api.post(`/recognition/${id}/reset`, {}).catch(() => {})
    running.current = true
    setScanning(true)
    ;(async () => {
      while (running.current) {
        const t0 = performance.now()
        const blob = await cam.capture(800, 0.8)
        if (blob && running.current) {
          try {
            const form = new FormData()
            form.append('file', blob, 'frame.jpg')
            const r = await api.postForm(`/recognition/${id}/frame`, form)
            setFaces(r.faces)
            if (r.newly_marked.length) {
              r.newly_marked.forEach((m) => toast(`${m.name} marked ${m.status}`))
              load()
            }
          } catch (e) {
            setError(e.message)
            if (e.status === 409 || e.status === 401 || e.status === 403 || e.status === 503) { stopScan(); break }
          }
        }
        await sleep(Math.max(0, FRAME_INTERVAL_MS - (performance.now() - t0)))
      }
    })()
  }

  useEffect(() => () => { running.current = false }, [])

  const closeSession = async () => {
    if (!confirm('Close this session? Students who were not recognised will be marked absent.')) return
    stopScan(); cam.stop()
    try { setDetail(await api.post(`/sessions/${id}/close`, {})) } catch (e) { setError(e.message) }
  }

  const manual = async (student_id, status) => {
    try { setDetail(await api.post(`/sessions/${id}/attendance/manual`, { student_id, status })) } catch (e) { setError(e.message) }
  }

  if (!detail) return <>{error ? <div className="notice bad">{error}</div> : <p className="muted">Loading…</p>}</>

  const { session, roster } = detail
  const open = session.status === 'open'
  const count = (s) => roster.filter((r) => r.status === s).length

  return (
    <>
      <Link to={`/courses/${session.course_id}`} className="back">← {detail.course_code}</Link>
      <h1>{session.title} <span className={`badge ${open ? 'good' : ''}`}>{session.status}</span></h1>
      <p className="muted">{detail.course_name} · started {fmt(session.starts_at)} · late after {session.late_after_minutes} min</p>
      {error && <div className="notice bad">{error}</div>}
      <div className="toasts">{toasts.map((t) => <div key={t.key} className="toast">✓ {t.text}</div>)}</div>

      <div className={open ? 'grid-2 wide-left' : ''}>
        {open && (
          <section className="card">
            <CameraView videoRef={cam.videoRef} state={cam.state} error={cam.error} faces={scanning ? faces : []} />
            <div className="toolbar">
              {!scanning
                ? <button className="btn primary" onClick={startScan}>Start scanning</button>
                : <button className="btn" onClick={stopScan}>Pause scanning</button>}
              {cam.state === 'on' && !scanning && <button className="btn ghost" onClick={cam.stop}>Stop camera</button>}
              <span className="spacer" />
              <button className="btn danger" onClick={closeSession}>Close session</button>
            </div>
            <p className="muted small">Each student looks at the camera, then turns their head to the left and to the right (liveness check). Attendance is recorded once per session.</p>
          </section>
        )}

        <section className="card">
          <div className="stats compact">
            <div className="stat"><b>{count('present')}</b><span>Present</span></div>
            <div className="stat"><b>{count('late')}</b><span>Late</span></div>
            <div className="stat"><b>{open ? count('pending') : count('absent')}</b><span>{open ? 'Pending' : 'Absent'}</span></div>
          </div>
          <table>
            <thead><tr><th>Roll no</th><th>Name</th><th>Status</th><th>{open ? 'Override' : 'Marked at'}</th></tr></thead>
            <tbody>
              {roster.length === 0 && <tr><td colSpan="4" className="muted">No students enrolled in this course.</td></tr>}
              {roster.map((r) => (
                <tr key={r.student_id}>
                  <td>{r.roll_no}</td><td>{r.name}</td>
                  <td><span className={`badge s-${r.status}`}>{r.status}</span>{r.method === 'manual' && <small className="muted"> manual</small>}</td>
                  <td>
                    {open
                      ? <select value="" onChange={(e) => e.target.value && manual(r.student_id, e.target.value)}>
                          <option value="">Set…</option><option value="present">Present</option><option value="late">Late</option><option value="absent">Absent</option>
                        </select>
                      : fmt(r.marked_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="toolbar">
            <button className="btn sm" onClick={() => api.download(`/reports/session/${id}/export?format=csv`, `session_${id}.csv`).catch((e) => setError(e.message))}>Export CSV</button>
            <button className="btn sm" onClick={() => api.download(`/reports/session/${id}/export?format=xlsx`, `session_${id}.xlsx`).catch((e) => setError(e.message))}>Export Excel</button>
          </div>
        </section>
      </div>
    </>
  )
}
