import { ArrowLeft, ArrowRight, CircleCheck, CircleQuestionMark, CircleX, MessageSquareText } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, useApi } from '../api.js'
import { CompareToggle, Empty, ErrorMessage, GuidanceNotice, Loading, RichText, SourceLink, StatusPlate } from '../components.jsx'
import { buildQuestions, describeAnswer, toProfile, validateAnswer } from '../eligibility.js'

function Question({ question, value, error, onChange, titleRef }) {
  const errorId = error ? 'answer-error' : undefined
  if (question.kind === 'choice') {
    return (
      <fieldset className="question question--fieldset" aria-describedby={errorId}>
        <legend ref={titleRef} tabIndex={-1}>
          {question.title}
        </legend>
        <div className="options options--inline">
          {question.options.map(([optionValue, label]) => (
            <label className="option" key={optionValue}>
              <input
                type="radio"
                name={question.key}
                value={optionValue}
                checked={value === optionValue}
                onChange={() => onChange(optionValue)}
              />
              {label}
            </label>
          ))}
        </div>
        {error && (
          <p id={errorId} className="field__error mt-s">
            {error}
          </p>
        )}
      </fieldset>
    )
  }
  return (
    <div className="question field">
      <label className="question__title" htmlFor="answer" ref={titleRef} tabIndex={-1}>
        {question.title}
      </label>
      {question.hint && (
        <span className="field__hint" id="answer-hint">
          {question.hint}
        </span>
      )}
      {question.kind === 'select' ? (
        <select
          id="answer"
          className="select"
          value={value ?? ''}
          aria-invalid={Boolean(error)}
          aria-describedby={errorId}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">Choose one</option>
          {question.options.map(([optionValue, label]) => (
            <option key={optionValue} value={optionValue}>
              {label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id="answer"
          className="input num"
          inputMode="numeric"
          autoComplete="off"
          value={value ?? ''}
          aria-invalid={Boolean(error)}
          aria-describedby={[question.hint ? 'answer-hint' : null, errorId].filter(Boolean).join(' ') || undefined}
          onChange={(event) => onChange(event.target.value.replace(/[,\s₹]/g, ''))}
        />
      )}
      {error && (
        <span id={errorId} className="field__error">
          {error}
        </span>
      )}
    </div>
  )
}

function ConditionList({ items, suffix }) {
  return (
    <ul>
      {items.map((c) => (
        <li key={`${c.field}-${c.requirement}`}>
          {c.requirement}
          {suffix(c)}
        </li>
      ))}
    </ul>
  )
}

function Result({ result, profile }) {
  const [explanation, setExplanation] = useState({ status: 'idle' })
  const explain = async () => {
    setExplanation({ status: 'loading' })
    try {
      const response = await api.explainEligibility(profile, result.schemeId)
      setExplanation({ status: 'done', text: response.explanation })
    } catch (error) {
      setExplanation({ status: 'error', error })
    }
  }
  const nothingComparable = !result.matched.length && !result.unmatched.length && !result.missing.length
  return (
    <li className="scheme-item">
      <div>
        <StatusPlate status={result.status} />
      </div>
      <h3>
        <Link to={`/schemes/${encodeURIComponent(result.schemeId)}`}>{result.name}</Link>
      </h3>
      {result.description && <p className="scheme-item__desc">{result.description}</p>}
      <dl className="reasons">
        {result.matched.length > 0 && (
          <div>
            <dt className="reason--match">
              <CircleCheck size={18} aria-hidden="true" /> Conditions you meet
            </dt>
            <dd>
              <ConditionList items={result.matched} suffix={(c) => ` (you: ${c.yourValue})`} />
            </dd>
          </div>
        )}
        {result.unmatched.length > 0 && (
          <div>
            <dt className="reason--no">
              <CircleX size={18} aria-hidden="true" /> Conditions you do not meet
            </dt>
            <dd>
              <ConditionList items={result.unmatched} suffix={(c) => ` (you: ${c.yourValue})`} />
            </dd>
          </div>
        )}
        {result.missing.length > 0 && (
          <div>
            <dt className="reason--missing">
              <CircleQuestionMark size={18} aria-hidden="true" /> Information not provided
            </dt>
            <dd>
              <ConditionList items={result.missing} suffix={() => ' (you did not answer this)'} />
            </dd>
          </div>
        )}
        {nothingComparable && (
          <div>
            <dt>No conditions could be compared</dt>
            <dd>
              This scheme's conditions are not stored in a form that can be compared. Read its official eligibility
              criteria.
            </dd>
          </div>
        )}
      </dl>
      {explanation.status === 'done' && (
        <div className="simple" aria-live="polite">
          <span className="label">In simple words · written by AI from the result above</span>
          <RichText text={explanation.text} />
        </div>
      )}
      {explanation.status === 'error' && <ErrorMessage error={explanation.error} />}
      <div className="scheme-item__foot">
        <SourceLink url={result.sourceUrl} />
        <div className="inline-actions mt-0">
          {explanation.status !== 'done' && !nothingComparable && (
            <button type="button" className="button button--outline button--small" onClick={explain} disabled={explanation.status === 'loading'}>
              {explanation.status === 'loading' ? <span className="spinner" aria-hidden="true" /> : <MessageSquareText size={18} aria-hidden="true" />}
              Explain this result
            </button>
          )}
          <CompareToggle schemeId={result.schemeId} name={result.name} />
        </div>
      </div>
    </li>
  )
}

export default function EligibilityPage() {
  const [params] = useSearchParams()
  const schemeId = params.get('scheme')
  const filters = useApi((signal) => api.filters(signal), [])
  const scheme = useApi((signal) => (schemeId ? api.scheme(schemeId, signal) : Promise.resolve(null)), [schemeId])

  const [phase, setPhase] = useState('questions')
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState({})
  const [error, setError] = useState('')
  const [check, setCheck] = useState({ status: 'idle' })
  const titleRef = useRef(null)
  const resultsRef = useRef(null)
  const moved = useRef(false)

  useEffect(() => {
    if (moved.current) titleRef.current?.focus()
  }, [step])
  useEffect(() => {
    if (phase === 'results') resultsRef.current?.focus()
  }, [phase])

  if (filters.error) {
    return (
      <div className="wrap">
        <ErrorMessage error={filters.error} onRetry={filters.retry} />
      </div>
    )
  }
  if (!filters.data) {
    return (
      <div className="wrap">
        <Loading label="Loading questions" />
        <div className="page-head" aria-hidden="true">
          <span className="skeleton" style={{ width: '60%', height: '2.4em' }} />
        </div>
      </div>
    )
  }

  const questions = buildQuestions(filters.data)
  const question = questions[step]
  const last = step === questions.length - 1

  const goTo = (next) => {
    moved.current = true
    setError('')
    setStep(next)
  }

  const submit = async (finalAnswers) => {
    setPhase('results')
    setCheck({ status: 'loading' })
    try {
      const body = { ...toProfile(finalAnswers), ...(schemeId ? { schemeIds: [schemeId] } : {}) }
      setCheck({ status: 'done', data: await api.checkEligibility(body) })
    } catch (err) {
      setCheck({ status: 'error', error: err })
    }
  }

  const next = (skip = false) => {
    let updated = answers
    if (skip) {
      updated = { ...answers, [question.key]: '' }
      setAnswers(updated)
    } else {
      const problem = validateAnswer(question, answers[question.key] ?? '')
      if (problem) {
        setError(problem)
        return
      }
    }
    if (last) submit(updated)
    else goTo(step + 1)
  }

  const answered = questions.filter((q) => answers[q.key])

  return (
    <div className="wrap">
      <header className="page-head">
        <h1 className="lettering">Check your eligibility</h1>
        <p>
          {schemeId && scheme.data
            ? `Checking one scheme: ${scheme.data.name}. `
            : 'We compare your answers with the stored conditions of every scheme. '}
          Skip any question you prefer not to answer.
        </p>
      </header>

      {phase === 'questions' && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            next()
          }}
          noValidate
        >
          <p className="fine num" aria-live="polite">
            Question {step + 1} of {questions.length}
          </p>
          <ol className="steps" aria-hidden="true">
            {questions.map((q, i) => (
              <li key={q.key} data-state={i < step ? 'done' : i === step ? 'current' : 'todo'} />
            ))}
          </ol>
          <Question
            key={question.key}
            question={question}
            value={answers[question.key]}
            error={error}
            titleRef={titleRef}
            onChange={(value) => {
              setError('')
              setAnswers({ ...answers, [question.key]: value })
            }}
          />
          <div className="flow-nav">
            {step > 0 && (
              <button type="button" className="button button--outline" onClick={() => goTo(step - 1)}>
                <ArrowLeft size={18} aria-hidden="true" /> Back
              </button>
            )}
            <button type="submit" className="button">
              {last ? 'See my results' : 'Next'} <ArrowRight size={18} aria-hidden="true" />
            </button>
            <button type="button" className="button button--link" onClick={() => next(true)}>
              Skip this question
            </button>
          </div>
        </form>
      )}

      {phase === 'results' && (
        <section aria-labelledby="results-title">
          <h2 id="results-title" className="section-title" ref={resultsRef} tabIndex={-1}>
            Your results
          </h2>
          <GuidanceNotice />
          <ul className="answers" aria-label="Your answers">
            {answered.map((q) => (
              <li className="tag" key={q.key}>
                {describeAnswer(q, answers[q.key])}
              </li>
            ))}
            {answered.length === 0 && <li className="tag">No questions answered</li>}
          </ul>
          <div className="inline-actions">
            <button
              type="button"
              className="button button--outline button--small"
              onClick={() => {
                setPhase('questions')
                goTo(0)
              }}
            >
              Change my answers
            </button>
          </div>

          {check.status === 'loading' && (
            <p role="status" className="fine mt-m">
              Comparing your answers with scheme conditions…
            </p>
          )}
          {check.status === 'error' && <ErrorMessage error={check.error} onRetry={() => submit(answers)} />}
          {check.status === 'done' && (
            <>
              {!schemeId && (
                <div className="summary-counts num" role="status">
                  <p>
                    <CircleCheck size={20} className="reason--match" aria-hidden="true" />
                    {check.data.likelyMatch} likely match
                  </p>
                  <p>
                    <CircleQuestionMark size={20} className="reason--missing" aria-hidden="true" />
                    {check.data.moreInfoNeeded} need more information
                  </p>
                  <p>
                    <CircleX size={20} className="reason--no" aria-hidden="true" />
                    {check.data.notAMatch} not a match
                  </p>
                </div>
              )}
              {check.data.results.length === 0 ? (
                <Empty title="No stored scheme fits these answers">
                  <p>This does not mean you are not eligible for any scheme. Try searching in your own words.</p>
                  <div className="inline-actions">
                    <Link to="/search">Search schemes</Link>
                  </div>
                </Empty>
              ) : (
                <>
                  {!schemeId && (
                    <p className="fine mt-s">
                      Showing schemes that do not conflict with your answers, the most matching conditions first.
                    </p>
                  )}
                  <ul className="results">
                    {check.data.results.map((result) => (
                      <Result key={result.schemeId} result={result} profile={toProfile(answers)} />
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </section>
      )}
    </div>
  )
}
