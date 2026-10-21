/** Mirrored webcam preview with recognition boxes drawn over it.
 *  Boxes arrive normalised (0..1) in un-mirrored image space, so x is flipped here. */
const LABELS = {
  verifying: 'Checking…',
  unknown: 'Unknown',
  turn_head: 'Turn head left, then right',
  marked: 'Marked',
  not_enrolled: 'Not in this course',
}

export default function CameraView({ videoRef, state, error, faces = [] }) {
  return (
    <div className="camera">
      <video ref={videoRef} playsInline muted className={state === 'on' ? 'mirrored' : 'hidden'} />
      {state !== 'on' && (
        <div className="camera-empty">
          {state === 'starting' ? 'Starting camera…' : error || 'Camera is off'}
        </div>
      )}
      {state === 'on' && faces.map((f) => {
        const [x, y, w, h] = f.box
        const name = f.student ? f.student.name : ''
        const label = f.status === 'marked' ? `✓ ${name}` : f.status === 'not_enrolled' ? `${name} — ${LABELS.not_enrolled}` : f.status === 'turn_head' ? `${name}: ${LABELS.turn_head}` : LABELS[f.status]
        return (
          <div key={f.track_id} className={`facebox ${f.status}`}
            style={{ left: `${(1 - x - w) * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` }}>
            <span className="facelabel">
              {label}
              {f.status === 'turn_head' && (
                <span className="chips">
                  <i className={f.liveness.left ? 'ok' : ''}>◀</i>
                  <i className={f.liveness.right ? 'ok' : ''}>▶</i>
                </span>
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}
