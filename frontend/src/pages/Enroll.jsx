import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import CameraView from '../components/CameraView.jsx'
import { sleep, useWebcam } from '../useWebcam'

const STEPS = [
  { pose: 'front', title: 'Look straight at the camera', hint: 'Neutral expression, face centred, good light on your face.' },
  { pose: 'left', title: 'Turn your head slightly to one side', hint: 'About 30°. Keep your eyes on the screen.' },
  { pose: 'right', title: 'Turn your head slightly to the other side', hint: 'About 30° the other way.' },
]
const SHOTS = 5

export default function Enroll() {
  const { id } = useParams()
  const cam = useWebcam()
  const [student, setStudent] = useState(null)
  const [summary, setSummary] = useState({ total: 0, by_pose: {} })
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [results, setResults] = useState([])
  const [error, setError] = useState('')

  const refresh = () => api.get(`/students/${id}/biometrics`).then(setSummary)
  useEffect(() => {
    api.get('/students').then((all) => setStudent(all.find((s) => String(s.id) === id) || null)).catch((e) => setError(e.message))
    refresh().catch(() => {})
  }, [id])

  const capture = async () => {
    setBusy(true)
    setError('')
    setResults([])
    try {
      const form = new FormData()
      for (let i = 0; i < SHOTS; i++) {
        const blob = await cam.capture(960, 0.9)
        if (blob) form.append('files', blob, `shot${i}.jpg`)
        await sleep(350)
      }
      const res = await api.postForm(`/students/${id}/enroll-face`, form)
      setResults(res.results)
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const s = STEPS[step]
  return (
    <>
      <Link to="/students" className="back">← Students</Link>
      <h1>Enrol face{student ? `: ${student.name}` : ''}</h1>
      {error && <div className="notice bad">{error}</div>}

      <div className="grid-2">
        <section className="card">
          <CameraView videoRef={cam.videoRef} state={cam.state} error={cam.error} />
          <div className="toolbar">
            {cam.state !== 'on'
              ? <button className="btn primary" onClick={cam.start}>Start camera</button>
              : <button className="btn ghost" onClick={cam.stop}>Stop camera</button>}
          </div>
        </section>

        <section className="card">
          <div className="steps">
            {STEPS.map((x, i) => <button key={x.pose} className={`step ${i === step ? 'current' : ''}`} onClick={() => setStep(i)}>{i + 1}</button>)}
          </div>
          <h2>{s.title}</h2>
          <p className="muted">{s.hint}</p>
          <button className="btn primary" disabled={cam.state !== 'on' || busy} onClick={capture}>
            {busy ? 'Capturing…' : `Capture ${SHOTS} photos`}
          </button>
          {results.length > 0 && (
            <ul className="results">
              {results.map((r, i) => (
                <li key={i} className={r.accepted ? 'ok' : 'bad'}>
                  {r.accepted ? `Photo ${i + 1}: accepted (${r.pose})` : `Photo ${i + 1}: ${r.reasons.join(', ')}`}
                </li>
              ))}
            </ul>
          )}
          <hr />
          <p><b>{summary.total}</b> templates stored
            {Object.keys(summary.by_pose).length > 0 && <span className="muted"> — {Object.entries(summary.by_pose).map(([p, n]) => `${p}: ${n}`).join(', ')}</span>}
          </p>
          <p className="muted small">Photos are analysed in memory and discarded. Only an encrypted numeric template is saved. Aim for 3+ templates per pose.</p>
          <div className="toolbar">
            {step < STEPS.length - 1
              ? <button className="btn" onClick={() => { setStep(step + 1); setResults([]) }}>Next step →</button>
              : <Link className="btn primary" to="/students">Finish</Link>}
          </div>
        </section>
      </div>
    </>
  )
}
