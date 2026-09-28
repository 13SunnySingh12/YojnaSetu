import {
  CircleCheck,
  CircleQuestionMark,
  CircleX,
  ExternalLink,
  Info,
  Plus,
  RotateCcw,
  TriangleAlert,
  Check,
} from 'lucide-react'
import { Component } from 'react'
import { Link } from 'react-router'
import { useCompare } from './compare.jsx'

/** Replaces a crashed page with a plain message instead of a blank screen; header and footer stay. */
export class ErrorBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="wrap">
        <div className="callout callout--error" role="alert">
          <TriangleAlert size={22} aria-hidden="true" />
          <div>
            <p>Sorry, this page stopped working. Please reload the page or go back to the home page.</p>
            <a href="/">Go to the home page</a>
          </div>
        </div>
      </div>
    )
  }
}

export const NOT_AVAILABLE = 'Not available from the official source'

const BOLD = /\*\*(.+?)\*\*/g
const WEB_LINK = /(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g

function linkify(text, keyPrefix) {
  return text.split(WEB_LINK).map((part, i) =>
    i % 2 === 1 ? (
      <a key={`${keyPrefix}-${i}`} href={part} target="_blank" rel="noopener noreferrer">
        {part}
      </a>
    ) : (
      part
    ),
  )
}

/** Stored or generated text rendered safely: **bold** and plain web links; line breaks are kept by CSS. */
export function RichText({ text }) {
  return text
    .split(BOLD)
    .map((piece, i) => (i % 2 === 1 ? <strong key={i}>{linkify(piece, i)}</strong> : linkify(piece, i)))
}

/** Official wording exactly as stored, or a plain statement that the source did not provide it. */
export function OfficialText({ text, as: Tag = 'p' }) {
  if (!text || !text.trim()) {
    return <Tag className="official official--missing">{NOT_AVAILABLE}</Tag>
  }
  return (
    <Tag className="official">
      <RichText text={text} />
    </Tag>
  )
}

const STATUS = {
  LIKELY_MATCH: { label: 'Likely match', className: 'status--likely', Icon: CircleCheck },
  NOT_A_MATCH: { label: 'Not a match', className: 'status--no', Icon: CircleX },
  MORE_INFO_NEEDED: { label: 'More information needed', className: 'status--info', Icon: CircleQuestionMark },
}

export function StatusPlate({ status }) {
  const { label, className, Icon } = STATUS[status] ?? STATUS.MORE_INFO_NEEDED
  return (
    <span className={`status status--stamp ${className}`}>
      <Icon size={22} strokeWidth={2.5} aria-hidden="true" />
      {label}
    </span>
  )
}

/** Fixed text, rendered by the app with every eligibility result; never generated. */
export function GuidanceNotice() {
  return (
    <aside className="notice" aria-label="Guidance notice">
      <Info size={26} strokeWidth={2.25} aria-hidden="true" />
      <div>
        <strong>This is guidance only, not a decision.</strong>
        <p>
          YojnaSetu compares your answers with the scheme conditions it has stored. It does not approve
          applications or confirm eligibility. The concerned government department makes the final decision,
          so always check the official source before you apply.
        </p>
      </div>
    </aside>
  )
}

export function SourceLink({ url, name }) {
  if (!url) return null
  return (
    <a className="source-link" href={url} target="_blank" rel="noopener noreferrer">
      Official source{name ? `: ${name}` : ''}
      <ExternalLink size={16} aria-hidden="true" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  )
}

export function CompareToggle({ schemeId, name }) {
  const compare = useCompare()
  const selected = compare.has(schemeId)
  const blocked = !selected && compare.full
  return (
    <button
      type="button"
      className="button button--outline button--small compare-toggle"
      aria-pressed={selected}
      aria-disabled={blocked}
      title={blocked ? 'You can compare up to 4 schemes' : undefined}
      onClick={() => !blocked && compare.toggle(schemeId)}
    >
      {selected ? <Check size={18} aria-hidden="true" /> : <Plus size={18} aria-hidden="true" />}
      {selected ? 'Added to compare' : blocked ? 'Compare list is full' : 'Compare'}
      <span className="sr-only"> {name}</span>
    </button>
  )
}

export function SchemeItem({ scheme, extra }) {
  const place = scheme.state ? `${scheme.state} (state scheme)` : scheme.level === 'Central' ? 'All India (central scheme)' : scheme.level
  return (
    <li className="scheme-item">
      <h3>
        <Link to={`/schemes/${encodeURIComponent(scheme.id)}`}>{scheme.name}</Link>
      </h3>
      {scheme.description && <p className="scheme-item__desc">{scheme.description}</p>}
      <ul className="meta" aria-label="Scheme facts">
        {place && <li className="tag tag--indigo">{place}</li>}
        {(scheme.categories ?? []).slice(0, 2).map((c) => (
          <li className="tag" key={c}>
            {c}
          </li>
        ))}
        {extra}
      </ul>
      <div className="scheme-item__foot">
        <SourceLink url={scheme.sourceUrl} name={scheme.sourceName} />
        <CompareToggle schemeId={scheme.id} name={scheme.name} />
      </div>
    </li>
  )
}

export function ErrorMessage({ error, onRetry }) {
  return (
    <div className="callout callout--error" role="alert">
      <TriangleAlert size={22} aria-hidden="true" />
      <div>
        <p>{error?.message ?? 'Something went wrong. Please try again.'}</p>
        {error?.errors?.length > 0 && (
          <ul>
            {error.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        )}
        {onRetry && (
          <button type="button" className="button button--link" onClick={onRetry}>
            <RotateCcw size={16} aria-hidden="true" /> Try again
          </button>
        )}
      </div>
    </div>
  )
}

export function ListSkeleton({ rows = 3 }) {
  return (
    <div className="results" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div className="scheme-item" key={i}>
          <span className="skeleton" style={{ width: '60%', height: '1.4em' }} />
          <span className="skeleton" style={{ width: '95%' }} />
          <span className="skeleton" style={{ width: '80%' }} />
        </div>
      ))}
    </div>
  )
}

export function Loading({ label }) {
  return (
    <p className="sr-only" role="status">
      {label}
    </p>
  )
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children}
    </div>
  )
}

export function Pager({ page, size, total, onPage }) {
  const pages = Math.ceil(total / size)
  if (pages <= 1) return null
  return (
    <nav className="pager" aria-label="Result pages">
      <button type="button" className="button button--outline button--small" disabled={page === 0} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span className="num">
        Page {page + 1} of {pages}
      </span>
      <button
        type="button"
        className="button button--outline button--small"
        disabled={page + 1 >= pages}
        onClick={() => onPage(page + 1)}
      >
        Next
      </button>
    </nav>
  )
}
