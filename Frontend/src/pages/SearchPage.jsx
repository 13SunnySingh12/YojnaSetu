import { Info, Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, useApi } from '../api.js'
import { Empty, ErrorMessage, ListSkeleton, Loading, Pager, SchemeItem } from '../components.jsx'

function SearchForm({ initial, onSearch }) {
  const [draft, setDraft] = useState(initial)
  return (
    <form
      role="search"
      className="search-row"
      onSubmit={(event) => {
        event.preventDefault()
        if (draft.trim().length >= 2) onSearch(draft.trim())
      }}
    >
      <label htmlFor="search-q" className="sr-only">
        Search schemes
      </label>
      <input
        id="search-q"
        className="input"
        type="search"
        enterKeyHint="search"
        placeholder="e.g. loan for starting a tailoring shop in a village"
        minLength={2}
        maxLength={200}
        required
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
      <button type="submit" className="button">
        <Search size={20} aria-hidden="true" /> Search
      </button>
    </form>
  )
}

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = (params.get('q') ?? '').trim()
  const page = Math.max(0, Number.parseInt(params.get('page') ?? '0', 10) || 0)
  const result = useApi((signal) => (q.length >= 2 ? api.search(q, page, signal) : Promise.resolve(null)), [q, page])

  return (
    <div className="wrap">
      <header className="page-head">
        <h1 className="lettering">Search schemes</h1>
        <p>Search by scheme name or describe your need in everyday words.</p>
      </header>
      {/* Keyed on the URL query so the box resets when the query changes elsewhere (back button, links). */}
      <SearchForm key={q} initial={q} onSearch={(text) => setParams({ q: text })} />

      {q.length < 2 && (
        <Empty title="What are you looking for?">
          <p>Try "scholarship for girls", "pension for elderly parents" or a scheme name.</p>
          <div className="inline-actions">
            <Link to="/schemes">Browse all schemes</Link>
            <Link to="/eligibility">Answer eligibility questions</Link>
          </div>
        </Empty>
      )}

      {q.length >= 2 && (
        <section aria-labelledby="results-title">
          <h2 id="results-title" className="section-title">
            {result.data ? (
              <span className="num">
                {result.data.total} {result.data.total === 1 ? 'scheme' : 'schemes'} for "{q}"
              </span>
            ) : (
              <>Results for "{q}"</>
            )}
          </h2>
          {result.loading && <Loading label="Searching schemes" />}
          {result.data && !result.data.semanticAvailable && (
            <p className="callout" role="status">
              <Info size={20} aria-hidden="true" />
              Showing exact word matches only. Search by meaning is not available right now.
            </p>
          )}
          {result.error && <ErrorMessage error={result.error} onRetry={result.retry} />}
          {result.loading && !result.data && <ListSkeleton />}
          {result.data && result.data.items.length === 0 && (
            <Empty title="No schemes matched">
              <p>Try other words, browse by category, or ask your question in your own words.</p>
              <div className="inline-actions">
                <Link to="/schemes">Browse schemes</Link>
                <Link to={`/ask?q=${encodeURIComponent(q)}`}>Ask this as a question</Link>
              </div>
            </Empty>
          )}
          {result.data && result.data.items.length > 0 && (
            <>
              <ul className="results" aria-busy={result.loading}>
                {result.data.items.map(({ scheme, matchedByKeyword, matchedByMeaning }) => (
                  <SchemeItem
                    key={scheme.id}
                    scheme={scheme}
                    extra={
                      <>
                        {matchedByKeyword && <li className="tag">Matches your words</li>}
                        {matchedByMeaning && <li className="tag">Similar meaning</li>}
                      </>
                    }
                  />
                ))}
              </ul>
              <Pager
                page={result.data.page}
                size={result.data.size}
                total={result.data.total}
                onPage={(next) => setParams({ q, page: String(next) })}
              />
            </>
          )}
        </section>
      )}
    </div>
  )
}
