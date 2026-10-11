export type Json = Record<string, unknown>

export class MiniBknApi {
  constructor(public baseUrl: string, private apiKey = '') {}

  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl.replace(/\/$/, '')}${path}`, {
      ...init,
      headers: {
        'content-type': 'application/json',
        ...(this.apiKey ? { 'x-api-key': this.apiKey } : {}),
        ...init?.headers,
      },
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      const message = payload.message ?? payload.detail ?? `请求失败（${response.status}）`
      throw new Error(String(message))
    }
    return payload as T
  }

  get<T>(path: string) {
    return this.request<T>(path)
  }

  post<T>(path: string, body: Json = {}) {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) })
  }

  patch<T>(path: string, body: Json) {
    return this.request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
  }
}
