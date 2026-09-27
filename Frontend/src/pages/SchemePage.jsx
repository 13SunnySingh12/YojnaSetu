import { ExternalLink, ListChecks, MessageCircleQuestion, MessageSquareText } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, useApi } from '../api.js'
import {
  CompareToggle,
  Empty,
  ErrorMessage,
  ListSkeleton,
  Loading,
  OfficialText,
  RichText,
  SchemeItem,
  SourceLink,
} from '../components.jsx'

// Same blocks in the same order for every scheme, so people know where to look.
const SECTIONS = [
  { key: 'description', title: 'About the scheme' },
  { key: 'details', title: 'Full description', optional: true },
  { key: 'eligibilityText', title: 'Who can apply' },
  { key: 'benefits', title: 'Benefits' },
  { key: 'documents', title: 'Documents required' },
  { key: 'applicationProcess', title: 'How to apply' },
  { key: 'conditions', title: 'Important conditions' },
]

function Explainable({ schemeId, section, text }) {
  const [state, setState] = useState({ status: 'idle' })

  const explain = async () => {
    setState({ status: 'loading' })
    try {
      const result = await api.explain(schemeId, section)
      setState({ status: 'done', explanation: result.explanation })
    } catch (error) {
      setState({ status: 'error', error })
    }
  }

  if (!text || !text.trim()) {
    return <OfficialText text={text} />
  }
  const shown = state.status === 'done'
  return (
    <>
      <div className={shown ? 'split' : undefined}>
        <div>
          {shown && <span className="label">Official text</span>}
          <OfficialText text={text} />
        </div>
        {shown && (
          <div className="simple" aria-live="polite">
            <span className="label">In simple words · written by AI from the official text</span>
            {state.explanation ? (
              <RichText text={state.explanation} />
            ) : (
              'A simpler version could not be made for this text. Please read the official text.'
            )}
          </div>
        )}
      </div>
      {state.status === 'error' && <ErrorMessage error={state.error} />}
      {!shown && (
        <div className="inline-actions">
          <button type="button" className="button button--outline button--small" onClick={explain} disabled={state.status === 'loading'}>
            {state.status === 'loading' ? <span className="spinner" aria-hidden="true" /> : <MessageSquareText size={18} aria-hidden="true" />}
            {state.status === 'loading' ? 'Explaining…' : 'Explain simply'}
          </button>
        </div>
      )}
    </>
  )
}

function Related({ schemeId }) {
  const related = useApi((signal) => api.related(schemeId, signal), [schemeId])
  if (related.loading && !related.data) return <ListSkeleton rows={2} />
  if (related.error || !related.data) return null
  if (!related.data.available) {
    return <p className="fine">Related schemes are not available right now.</p>
  }
  if (related.data.items.length === 0) {
    return <p className="fine">No closely related schemes were found.</p>
  }
  return (
    <ul className="results">
      {related.data.items.map((scheme) => (
        <SchemeItem key={scheme.id} scheme={scheme} />
      ))}
    </ul>
  )
}

export default function SchemePage() {
  const { id } = useParams()
  const scheme = useApi((signal) => api.scheme(id, signal), [id])
  const data = scheme.data?.id === id ? scheme.data : null

  useEffect(() => {
    document.title = data ? `${data.name} · YojnaSetu` : 'Scheme · YojnaSetu'
    return () => {
      document.title = 'YojnaSetu - Government scheme finder'
    }
  }, [data])

  if (scheme.error?.status === 404) {
    return (
      <div className="wrap">
        <Empty title="This scheme was not found">
          <p>It may have been withdrawn by the official source, or the link may be wrong.</p>
          <div className="inline-actions">
            <Link to="/search">Search schemes</Link>
          </div>
        </Empty>
      </div>
    )
  }
  if (scheme.error) {
    return (
      <div className="wrap">
        <ErrorMessage error={scheme.error} onRetry={scheme.retry} />
      </div>
    )
  }
  if (!data) {
    return (
      <div className="wrap">
        <Loading label="Loading scheme" />
        <div className="scheme-head" aria-hidden="true">
          <span className="skeleton" style={{ width: '70%', height: '2.4em' }} />
        </div>
        <ListSkeleton rows={3} />
      </div>
    )
  }

  const sections = SECTIONS.filter((s) => !(s.optional && !data[s.key]))
  const place = data.state ? `${data.state} (state scheme)` : data.level === 'Central' ? 'All India (central scheme)' : data.level

  return (
    <div className="wrap">
      <header className="scheme-head">
        <h1 className="lettering">{data.name}</h1>
        <ul className="meta" aria-label="Scheme facts">
          {place && <li className="tag tag--indigo">{place}</li>}
          {data.ministry && <li className="tag">{data.ministry}</li>}
          {(data.categories ?? []).map((c) => (
            <li className="tag" key={c}>
              {c}
            </li>
          ))}
        </ul>
        <div className="inline-actions">
          <a className="button" href={data.sourceUrl} target="_blank" rel="noopener noreferrer">
            Open official page <ExternalLink size={18} aria-hidden="true" />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
          <Link className="button button--outline" to={`/eligibility?scheme=${encodeURIComponent(data.id)}`}>
            <ListChecks size={18} aria-hidden="true" /> Check my eligibility
          </Link>
          <Link className="button button--outline" to={`/ask?scheme=${encodeURIComponent(data.id)}`}>
            <MessageCircleQuestion size={18} aria-hidden="true" /> Ask about this scheme
          </Link>
          <CompareToggle schemeId={data.id} name={data.name} />
        </div>
        <nav className="section-nav" aria-label="Parts of this scheme">
          {sections.map((s) => (
            <a key={s.key} href={`#${s.key}`}>
              {s.title}
            </a>
          ))}
          {data.faqs?.length > 0 && <a href="#faqs">Questions</a>}
          <a href="#source">Official source</a>
        </nav>
      </header>

      {sections.map((s) => (
        <section className="module" id={s.key} key={`${data.id}:${s.key}`} aria-labelledby={`${s.key}-title`}>
          <h2 className="module__tab" id={`${s.key}-title`}>
            {s.title}
          </h2>
          <div className="module__body">
            <Explainable schemeId={data.id} section={s.key} text={data[s.key]} />
          </div>
        </section>
      ))}

      {data.faqs?.length > 0 && (
        <section className="module" id="faqs" aria-labelledby="faqs-title">
          <h2 className="module__tab" id="faqs-title">
            Common questions
          </h2>
          <dl className="module__body reasons">
            {data.faqs.map((faq) => (
              <div key={faq.question}>
                <dt>{faq.question}</dt>
                <dd>
                  <OfficialText text={faq.answer} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <section className="module" id="source" aria-labelledby="source-title">
        <h2 className="module__tab" id="source-title">
          Official source
        </h2>
        <div className="module__body">
          <p>
            Everything on this page comes from <strong>{data.sourceName}</strong>. Confirm the details and apply on
            the official website.
          </p>
          <div className="inline-actions">
            <SourceLink url={data.sourceUrl} name={data.sourceName} />
          </div>
          {data.references?.length > 0 && (
            <>
              <span className="label mt-m">
                Official documents and links
              </span>
              <ul>
                {data.references.map((ref) => (
                  <li key={ref.url}>
                    <a href={ref.url} target="_blank" rel="noopener noreferrer">
                      {ref.title}
                    </a>
                  </li>
                ))}
              </ul>
            </>
          )}
          {data.syncedAt && (
            <p className="fine mt-s">
              Last copied from the official source on{' '}
              <time dateTime={data.syncedAt}>
                {new Date(data.syncedAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}
              </time>
              .
            </p>
          )}
        </div>
      </section>

      <h2 className="section-title">Related schemes</h2>
      <Related schemeId={data.id} />
    </div>
  )
}
