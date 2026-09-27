import { X } from 'lucide-react'
import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, useApi } from '../api.js'
import { Empty, ErrorMessage, Loading, NOT_AVAILABLE, OfficialText, SourceLink } from '../components.jsx'
import { MAX_COMPARE, useCompare } from '../compare.jsx'

const ROWS = [
  ['Where', (s) => (s.state ? `${s.state} (state scheme)` : s.level === 'Central' ? 'All India (central scheme)' : s.level)],
  ['Ministry', (s) => s.ministry],
  ['About', (s) => s.description, true],
  ['Who can apply', (s) => s.eligibilityText, true],
  ['Benefits', (s) => s.benefits, true],
  ['Documents', (s) => s.documents, true],
  ['How to apply', (s) => s.applicationProcess, true],
  ['Conditions', (s) => s.conditions, true],
]

export default function ComparePage() {
  const [params, setParams] = useSearchParams()
  const compare = useCompare()
  const fromUrl = (params.get('ids') ?? '').split(',').filter(Boolean).slice(0, MAX_COMPARE)
  const ids = fromUrl.length ? fromUrl : compare.ids
  const key = ids.join(',')

  // Keep the address shareable: it always names the schemes on screen.
  useEffect(() => {
    if (!fromUrl.length && compare.ids.length) setParams({ ids: compare.ids.join(',') }, { replace: true })
  }, [compare.ids]) // eslint-disable-line react-hooks/exhaustive-deps

  const schemes = useApi(
    (signal) =>
      Promise.allSettled(ids.map((id) => api.scheme(id, signal))).then((results) =>
        results.filter((r) => r.status === 'fulfilled').map((r) => r.value),
      ),
    [key],
  )

  const remove = (id) => {
    compare.remove(id)
    const rest = ids.filter((x) => x !== id)
    setParams(rest.length ? { ids: rest.join(',') } : {}, { replace: true })
  }

  return (
    <div className="wrap">
      <header className="page-head">
        <h1 className="lettering">Compare schemes</h1>
        <p>The same official details, row by row. Pick up to {MAX_COMPARE} schemes from search results or a scheme page.</p>
      </header>

      {ids.length === 0 && (
        <Empty title="No schemes chosen yet">
          <p>Use the Compare button on any scheme to add it here.</p>
          <div className="inline-actions">
            <Link to="/search">Search schemes</Link>
            <Link to="/schemes">Browse schemes</Link>
          </div>
        </Empty>
      )}
      {ids.length > 0 && schemes.loading && <Loading label="Loading schemes to compare" />}
      {schemes.error && <ErrorMessage error={schemes.error} onRetry={schemes.retry} />}
      {ids.length > 0 && schemes.loading && !schemes.data && <span className="skeleton" style={{ height: 320, marginTop: 16 }} />}
      {ids.length > 0 && schemes.data && (
        <div className="table-scroll" role="region" aria-label="Scheme comparison" tabIndex={0}>
          <table className="compare-table">
            <caption className="sr-only">Selected schemes compared by the same official fields</caption>
            <thead>
              <tr>
                <td />
                {schemes.data.map((s) => (
                  <th scope="col" key={s.id}>
                    <Link to={`/schemes/${encodeURIComponent(s.id)}`}>{s.name}</Link>
                    <div>
                      <button type="button" className="button button--link" onClick={() => remove(s.id)}>
                        <X size={16} aria-hidden="true" /> Remove<span className="sr-only"> {s.name}</span>
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROWS.map(([label, pick, official]) => (
                <tr key={label}>
                  <th scope="row">{label}</th>
                  {schemes.data.map((s) => (
                    <td key={s.id}>
                      {official ? <OfficialText text={pick(s)} /> : pick(s) || <span className="official--missing">{NOT_AVAILABLE}</span>}
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <th scope="row">Official source</th>
                {schemes.data.map((s) => (
                  <td key={s.id}>
                    <SourceLink url={s.sourceUrl} name={s.sourceName} />
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
      {schemes.data && schemes.data.length < ids.length && (
        <p className="fine mt-s">
          Some chosen schemes could not be loaded and are not shown.
        </p>
      )}
    </div>
  )
}
