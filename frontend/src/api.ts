// Токен запуска приходит в адресе после «#t=» и живёт только в памяти страницы.
const token = new URLSearchParams(location.hash.slice(1)).get('t')
if (token) history.replaceState(null, '', location.pathname)

/** Адрес картинки: <img> не умеет слать заголовок, поэтому токен идёт в ?t= (сервер принимает его только для GET). */
export function assetUrl(url: string): string {
  if (!token) return url
  return `${url}${url.includes('?') ? '&' : '?'}t=${encodeURIComponent(token)}`
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers['X-Studio-Token'] = token
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const r = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!r.ok) {
    let msg = `Ошибка ${r.status}`
    try {
      const j = await r.json()
      if (typeof j.detail === 'string') msg = j.detail
      else if (Array.isArray(j.detail)) msg = 'Проверьте поля формы'
    } catch { /* тело не JSON */ }
    throw new ApiError(r.status, msg)
  }
  return r.status === 204 ? (undefined as T) : r.json()
}

export const api = {
  get: <T>(url: string) => request<T>('GET', url),
  post: <T>(url: string, body?: unknown) => request<T>('POST', url, body ?? {}),
  patch: <T>(url: string, body: unknown) => request<T>('PATCH', url, body),
  put: <T>(url: string, body: unknown) => request<T>('PUT', url, body),
  del: <T = void>(url: string) => request<T>('DELETE', url),
}
