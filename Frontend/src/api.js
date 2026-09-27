import { useCallback, useEffect, useRef, useState } from 'react'

// Empty in development (Vite proxies /api); the Spring Boot URL in production builds.
const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const TIMEOUT_MS = 50_000

export class ApiError extends Error {
  constructor(message, status = 0, errors = []) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const timeout = AbortSignal.timeout(TIMEOUT_MS)
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    if (timeout.aborted) {
      throw new ApiError('This is taking too long. Please try again.')
    }
    throw new ApiError('Could not reach YojnaSetu. Check your internet connection and try again.')
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const message =
      response.status === 429
        ? 'Too many requests right now. Please wait a minute and try again.'
        : data?.detail || 'Something went wrong. Please try again.'
    throw new ApiError(message, response.status, data?.errors ?? [])
  }
  return data
}

function query(params) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

const id = (value) => encodeURIComponent(value)

export const api = {
  filters: (signal) => request('/api/filters', { signal }),
  schemes: (params, signal) => request(`/api/schemes${query(params)}`, { signal }),
  scheme: (schemeId, signal) => request(`/api/schemes/${id(schemeId)}`, { signal }),
  related: (schemeId, signal) => request(`/api/schemes/${id(schemeId)}/related`, { signal }),
  search: (q, page, signal) => request(`/api/search${query({ q, page })}`, { signal }),
  ask: (question, schemeId) => request('/api/ask', { method: 'POST', body: { question, schemeId } }),
  explain: (schemeId, section) =>
    request(`/api/schemes/${id(schemeId)}/explain`, { method: 'POST', body: { section } }),
  checkEligibility: (answers) => request('/api/eligibility/check', { method: 'POST', body: answers }),
  explainEligibility: (answers, schemeId) =>
    request('/api/eligibility/explain', { method: 'POST', body: { ...answers, schemeIds: [schemeId] } }),
}

/** Loads data for the current inputs; stale responses are cancelled when the inputs change. */
export function useApi(load, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [attempt, setAttempt] = useState(0)
  const loadRef = useRef(load)
  loadRef.current = load

  useEffect(() => {
    const controller = new AbortController()
    setState((previous) => ({ data: previous.data, error: null, loading: true }))
    loadRef
      .current(controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => {
        if (!controller.signal.aborted) setState({ data: null, error, loading: false })
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- callers pass their real inputs as deps
  }, [...deps, attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { ...state, retry }
}
