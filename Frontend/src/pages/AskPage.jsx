import { CircleQuestionMark, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, useApi } from '../api.js'
import { ErrorMessage, RichText, SourceLink } from '../components.jsx'

export default function AskPage() {
  const [params, setParams] = useSearchParams()
  const schemeId = params.get('scheme')
  const initial = params.get('q') ?? ''
  const scheme = useApi((signal) => (schemeId ? api.scheme(schemeId, signal) : Promise.resolve(null)), [schemeId])
  const [question, setQuestion] = useState(initial)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [answers, setAnswers] = useState([])
  const asked = useRef(false)
  const nextId = useRef(0)

  const ask = async (text) => {
    const trimmed = text.trim()
    if (trimmed.length < 3 || pending) return
    setPending(true)
    setError(null)
    try {
      const answer = await api.ask(trimmed, schemeId ?? undefined)
      nextId.current += 1
      setAnswers((previous) => [{ id: nextId.current, question: trimmed, ...answer }, ...previous])
      setQuestion('')
    } catch (err) {
      setError(err)
    } finally {
      setPending(false)
    }
  }

  // A question typed on the home page is asked straight away, once.
  useEffect(() => {
    if (initial && !asked.current) {
      asked.current = true
      ask(initial)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="wrap">
      <header className="page-head">
        <h1 className="lettering">Ask a question</h1>
        <p>Answers are written by AI using only the official scheme text stored in YojnaSetu, with the source shown.</p>
      </header>

      {schemeId && (
        <p className="callout callout--info">
          <span>
            Asking about: <strong>{scheme.data?.name ?? 'this scheme'}</strong>
          </span>
          <button
            type="button"
            className="button button--link callout__action"
            onClick={() => setParams({})}
          >
            <X size={16} aria-hidden="true" /> Ask about all schemes
          </button>
        </p>
      )}

      <form
        className="field mt-m"
        onSubmit={(event) => {
          event.preventDefault()
          ask(question)
        }}
      >
        <label htmlFor="ask-q">Your question</label>
        <textarea
          id="ask-q"
          className="input"
          rows={3}
          minLength={3}
          maxLength={500}
          required
          placeholder="e.g. What documents are needed to apply for a pension?"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <div className="inline-actions mt-xs">
          <button type="submit" className="button" disabled={pending || question.trim().length < 3}>
            {pending && <span className="spinner" aria-hidden="true" />}
            {pending ? 'Finding the answer…' : 'Ask'}
          </button>
          <span className="fine num">{question.length}/500</span>
        </div>
      </form>

      <div aria-live="polite">
        {pending && (
          <p role="status" className="fine mt-m">
            Looking through official scheme text…
          </p>
        )}
        {error && <ErrorMessage error={error} />}
      </div>

      {answers.map((answer) => (
        <article className="answer" key={answer.id}>
          <p className="answer__question">{answer.question}</p>
          {answer.grounded ? (
            <>
              <p className="answer__text">
                <RichText text={answer.answer} />
              </p>
              <p className="fine mt-s">
                Written by AI from official scheme text. Check the official source before you act on it.
              </p>
            </>
          ) : (
            <p className="callout">
              <CircleQuestionMark size={20} aria-hidden="true" />
              {answer.answer}
            </p>
          )}
          {answer.sources?.length > 0 && (
            <ul className="sources" aria-label="Sources">
              {answer.sources.map((source) => (
                <li key={source.schemeId}>
                  <Link to={`/schemes/${encodeURIComponent(source.schemeId)}`}>{source.name}</Link>
                  {' · '}
                  <SourceLink url={source.sourceUrl} />
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </div>
  )
}
