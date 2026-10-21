import { useCallback, useEffect, useRef, useState } from 'react'

/** Browser webcam access. The video is mirrored in CSS only; captured frames are NOT mirrored. */
export function useWebcam() {
  const videoRef = useRef(null)
  const [state, setState] = useState('idle') // idle | starting | on | error
  const [error, setError] = useState('')

  const stop = useCallback(() => {
    const v = videoRef.current
    if (v && v.srcObject) v.srcObject.getTracks().forEach((t) => t.stop())
    if (v) v.srcObject = null
    setState('idle')
  }, [])

  const start = useCallback(async () => {
    setError('')
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('This browser cannot access the camera (use https or localhost).')
      setState('error')
      return false
    }
    setState('starting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false,
      })
      const v = videoRef.current
      if (!v) { stream.getTracks().forEach((t) => t.stop()); return false }
      v.srcObject = stream
      await v.play()
      setState('on')
      return true
    } catch (e) {
      setError(e.name === 'NotAllowedError' ? 'Camera permission was denied.' : `Camera error: ${e.message}`)
      setState('error')
      return false
    }
  }, [])

  useEffect(() => stop, [stop])

  /** Grab the current frame as a JPEG blob, scaled to at most maxW pixels wide. */
  const capture = useCallback((maxW = 800, quality = 0.85) => new Promise((resolve) => {
    const v = videoRef.current
    if (!v || !v.videoWidth) return resolve(null)
    const scale = Math.min(1, maxW / v.videoWidth)
    const c = document.createElement('canvas')
    c.width = Math.round(v.videoWidth * scale)
    c.height = Math.round(v.videoHeight * scale)
    c.getContext('2d').drawImage(v, 0, 0, c.width, c.height)
    c.toBlob(resolve, 'image/jpeg', quality)
  }), [])

  return { videoRef, state, error, start, stop, capture }
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
