export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

export async function request<T>(path: string, method = 'GET', body?: unknown, timeoutMs = 12000): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`/api${path}`, {
      method, signal: controller.signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new ApiError(response.status, data?.error?.message || `Service returned ${response.status}.`)
    }
    return await response.json()
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new Error('Could not reach the service. Check the connection and reload trip state before trying again.')
  } finally { clearTimeout(timeout) }
}
