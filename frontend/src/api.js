const BASE = (import.meta.env.VITE_API_URL || '') + '/api'
const KEY = 'faceattend_token'

export const tokenStore = {
  get() { try { return localStorage.getItem(KEY) } catch { return null } },
  set(t) { try { localStorage.setItem(KEY, t) } catch { /* storage unavailable */ } },
  clear() { try { localStorage.removeItem(KEY) } catch { /* ignore */ } },
}

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

function messageFrom(body, fallback) {
  const d = body && body.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join('; ')
  return fallback
}

async function request(path, { method = 'GET', json, form } = {}) {
  const headers = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let body
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json) }
  if (form) body = form
  let res
  try {
    res = await fetch(BASE + path, { method, headers, body })
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running?', 0)
  }
  if (res.status === 401 && token) {
    tokenStore.clear()
    window.dispatchEvent(new Event('auth:logout'))
  }
  if (res.status === 204) return null
  const ct = res.headers.get('content-type') || ''
  const data = ct.includes('application/json') ? await res.json() : null
  if (!res.ok) throw new ApiError(messageFrom(data, `Request failed (${res.status})`), res.status)
  return data
}

export const api = {
  get: (p) => request(p),
  post: (p, json) => request(p, { method: 'POST', json }),
  postForm: (p, form) => request(p, { method: 'POST', form }),
  del: (p) => request(p, { method: 'DELETE' }),
  async download(path, filename) {
    const token = tokenStore.get()
    const res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) throw new ApiError(`Download failed (${res.status})`, res.status)
    const url = URL.createObjectURL(await res.blob())
    const a = Object.assign(document.createElement('a'), { href: url, download: filename })
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}

export const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : '—')
