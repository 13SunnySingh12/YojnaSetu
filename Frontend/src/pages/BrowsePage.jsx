import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, useApi } from '../api.js'
import { Empty, ErrorMessage, ListSkeleton, Loading, Pager, SchemeItem } from '../components.jsx'

const FIELDS = ['q', 'category', 'state', 'gender', 'age', 'beneficiaryType', 'level', 'need']

function fromParams(params) {
  return Object.fromEntries(FIELDS.map((key) => [key, params.get(key) ?? '']))
}

function FilterForm({ applied, options, onApply, onClear }) {
  const [draft, setDraft] = useState(applied)
  const [ageError, setAgeError] = useState('')
  return (
      <form
        className="filters"
        aria-label="Filter schemes"
        onSubmit={(event) => {
          event.preventDefault()
          const age = draft.age.trim()
          if (age && !(/^\d+$/.test(age) && Number(age) <= 120)) {
            setAgeError('Enter an age between 0 and 120.')
            return
          }
          setAgeError('')
          onApply(draft)
        }}
      >
        <div className="filters__grid">
          <div className="field">
            <label htmlFor="f-q">Keywords</label>
            <input id="f-q" className="input" value={draft.q} maxLength={200} onChange={(e) => setDraft({ ...draft, q: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="f-category">Category</label>
            <select id="f-category" className="select" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
              <option value="">All categories</option>
              {options?.categories.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-state">Your state</label>
            <select id="f-state" className="select" value={draft.state} onChange={(e) => setDraft({ ...draft, state: e.target.value })}>
              <option value="">Any state</option>
              {options?.states.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-need">Your situation</label>
            <select id="f-need" className="select" value={draft.need} onChange={(e) => setDraft({ ...draft, need: e.target.value })}>
              <option value="">Any situation</option>
              {options?.needs.map((n) => (
                <option key={n.key} value={n.key}>
                  {n.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-gender">Gender</label>
            <select id="f-gender" className="select" value={draft.gender} onChange={(e) => setDraft({ ...draft, gender: e.target.value })}>
              <option value="">Any gender</option>
              {options?.genders.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-age">Age</label>
            <input
              id="f-age"
              className="input num"
              inputMode="numeric"
              value={draft.age}
              aria-invalid={Boolean(ageError)}
              aria-describedby={ageError ? 'f-age-error' : undefined}
              onChange={(e) => setDraft({ ...draft, age: e.target.value })}
            />
            {ageError && (
              <span id="f-age-error" className="field__error">
                {ageError}
              </span>
            )}
          </div>
          <div className="field">
            <label htmlFor="f-beneficiary">Who applies</label>
            <select
              id="f-beneficiary"
              className="select"
              value={draft.beneficiaryType}
              onChange={(e) => setDraft({ ...draft, beneficiaryType: e.target.value })}
            >
              <option value="">Anyone</option>
              {options?.beneficiaryTypes.map((b) => (
                <option key={b}>{b}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-level">Level</label>
            <select id="f-level" className="select" value={draft.level} onChange={(e) => setDraft({ ...draft, level: e.target.value })}>
              <option value="">Central and state</option>
              {options?.levels.map((l) => (
                <option key={l}>{l}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="inline-actions mt-0">
          <button type="submit" className="button">
            Show schemes
          </button>
          <button type="button" className="button button--link" onClick={onClear}>
            Clear all filters
          </button>
        </div>
      </form>
  )
}

export default function BrowsePage() {
  const [params, setParams] = useSearchParams()
  const applied = fromParams(params)
  const page = Math.max(0, Number.parseInt(params.get('page') ?? '0', 10) || 0)
  const key = params.toString()

  const options = useApi((signal) => api.filters(signal), [])
  const result = useApi((signal) => api.schemes({ ...applied, page, size: 20 }, signal), [key])

  const apply = (values) => {
    const next = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== ''))
    setParams(next)
  }

  const need = options.data?.needs.find((n) => n.key === applied.need)
  const title = applied.category || (need ? `Schemes for: ${need.label}` : 'Browse all schemes')

  return (
    <div className="wrap">
      <header className="page-head">
        <h1 className="lettering">{title}</h1>
        <p>Narrow the list by your state, category or situation. Central schemes appear for every state.</p>
      </header>

      <FilterForm key={key} applied={applied} options={options.data} onApply={apply} onClear={() => setParams({})} />

      <section aria-labelledby="browse-results">
        <h2 id="browse-results" className="section-title">
          {result.data ? (
            <span className="num">
              {result.data.total} {result.data.total === 1 ? 'scheme' : 'schemes'}
            </span>
          ) : (
            'Schemes'
          )}
        </h2>
        {result.loading && <Loading label="Loading schemes" />}
        {result.error && <ErrorMessage error={result.error} onRetry={result.retry} />}
        {result.loading && !result.data && <ListSkeleton />}
        {result.data && result.data.items.length === 0 && (
          <Empty title="No schemes match these filters">
            <p>Remove a filter, or describe your need in your own words.</p>
            <div className="inline-actions">
              <button type="button" className="button button--link" onClick={() => setParams({})}>
                Clear all filters
              </button>
              <Link to="/search">Search in your own words</Link>
            </div>
          </Empty>
        )}
        {result.data && result.data.items.length > 0 && (
          <>
            <ul className="results" aria-busy={result.loading}>
              {result.data.items.map((scheme) => (
                <SchemeItem key={scheme.id} scheme={scheme} />
              ))}
            </ul>
            <Pager
              page={result.data.page}
              size={result.data.size}
              total={result.data.total}
              onPage={(next) => setParams({ ...Object.fromEntries(params), page: String(next) })}
            />
          </>
        )}
      </section>
    </div>
  )
}
