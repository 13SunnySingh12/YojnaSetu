import { createContext, useContext, useEffect, useMemo, useState } from 'react'

const CompareContext = createContext(null)
const KEY = 'yojnasetu.compare'
// oxlint-disable-next-line react/only-export-components
export const MAX_COMPARE = 4

function saved() {
  try {
    const ids = JSON.parse(sessionStorage.getItem(KEY))
    return Array.isArray(ids) ? ids.slice(0, MAX_COMPARE) : []
  } catch {
    return []
  }
}

/** Schemes picked for side-by-side comparison; kept for this browser tab only. */
export function CompareProvider({ children }) {
  const [ids, setIds] = useState(saved)

  useEffect(() => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(ids))
    } catch {
      // Storage can be unavailable (private mode); the selection still works in memory.
    }
  }, [ids])

  const value = useMemo(
    () => ({
      ids,
      full: ids.length >= MAX_COMPARE,
      has: (id) => ids.includes(id),
      toggle: (id) =>
        setIds((current) =>
          current.includes(id)
            ? current.filter((x) => x !== id)
            : current.length >= MAX_COMPARE
              ? current
              : [...current, id],
        ),
      remove: (id) => setIds((current) => current.filter((x) => x !== id)),
      clear: () => setIds([]),
    }),
    [ids],
  )
  return <CompareContext value={value}>{children}</CompareContext>
}

// The hook lives beside its provider (standard context pattern); fast refresh just reloads this file.
// oxlint-disable-next-line react/only-export-components
export function useCompare() {
  return useContext(CompareContext)
}
