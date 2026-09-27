import {
  ArrowRight,
  Baby,
  Banknote,
  Briefcase,
  Bus,
  Droplet,
  FlaskConical,
  GraduationCap,
  HandHeart,
  HeartPulse,
  House,
  Plane,
  Search,
  Shield,
  Sprout,
  Store,
  Tag,
  Trophy,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, useApi } from '../api.js'
import { Empty, ErrorMessage } from '../components.jsx'

const CATEGORY_ICONS = [
  [/agri|rural|farm/i, Sprout],
  [/educat|learn/i, GraduationCap],
  [/health|wellness/i, HeartPulse],
  [/hous|shelter/i, House],
  [/skill|employ/i, Briefcase],
  [/women|child/i, Baby],
  [/social|welfare/i, HandHeart],
  [/business|entrepreneur/i, Store],
  [/bank|financ|insur/i, Banknote],
  [/transport|infrastructure/i, Bus],
  [/sport|culture/i, Trophy],
  [/science|communication/i, FlaskConical],
  [/safety|law|justice/i, Shield],
  [/travel|tourism/i, Plane],
  [/utility|sanitation/i, Droplet],
]

function categoryIcon(name) {
  return CATEGORY_ICONS.find(([pattern]) => pattern.test(name))?.[1] ?? Tag
}

export default function HomePage() {
  const navigate = useNavigate()
  const filters = useApi((signal) => api.filters(signal), [])
  const [q, setQ] = useState('')
  const [question, setQuestion] = useState('')

  return (
    <div className="wrap">
      <section className="board board--indigo board--framed home-hero mt-l" aria-labelledby="find-title">
        <h1 id="find-title" className="lettering">
          Find government schemes that fit you
        </h1>
        <p>Type what you need in your own words. We look through official scheme records by words and by meaning.</p>
        <form
          role="search"
          className="search-row"
          onSubmit={(event) => {
            event.preventDefault()
            if (q.trim().length >= 2) navigate(`/search?q=${encodeURIComponent(q.trim())}`)
          }}
        >
          <label htmlFor="home-q" className="sr-only">
            What do you need help with?
          </label>
          <input
            id="home-q"
            className="input"
            type="search"
            enterKeyHint="search"
            placeholder="e.g. help with my daughter's school fees"
            minLength={2}
            maxLength={200}
            required
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
          <button type="submit" className="button button--light">
            <Search size={20} aria-hidden="true" /> Search
          </button>
        </form>
      </section>

      <div className="board-row">
        <section className="board board--marigold" aria-labelledby="check-title">
          <h2 id="check-title" className="lettering">
            Check what you may qualify for
          </h2>
          <p>
            Answer up to six short questions. We compare your answers with each scheme's official conditions and
            show the reasons.
          </p>
          <div className="inline-actions">
            <Link to="/eligibility" className="button">
              Start the questions <ArrowRight size={20} aria-hidden="true" />
            </Link>
          </div>
        </section>

        <section className="board board--leaf" aria-labelledby="ask-title">
          <h2 id="ask-title" className="lettering">
            Ask in your own words
          </h2>
          <p>Get a short answer written only from official scheme text, with its source.</p>
          <form
            className="search-row"
            onSubmit={(event) => {
              event.preventDefault()
              if (question.trim().length >= 3) navigate(`/ask?q=${encodeURIComponent(question.trim())}`)
            }}
          >
            <label htmlFor="home-ask" className="sr-only">
              Your question
            </label>
            <input
              id="home-ask"
              className="input"
              placeholder="e.g. Documents for a crop loan?"
              minLength={3}
              maxLength={500}
              required
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button type="submit" className="button button--light">
              Ask
            </button>
          </form>
        </section>
      </div>

      <h2 className="section-title">Browse by category</h2>
      {filters.loading && !filters.data && (
        <div className="plates" aria-hidden="true">
          {Array.from({ length: 8 }, (_, i) => (
            <span key={i} className="skeleton" style={{ minHeight: 104 }} />
          ))}
        </div>
      )}
      {filters.error && <ErrorMessage error={filters.error} onRetry={filters.retry} />}
      {filters.data && filters.data.categories.length === 0 && (
        <Empty title="No schemes are loaded yet">
          <p>Scheme records appear here once they have been imported from the official sources.</p>
        </Empty>
      )}
      {filters.data && filters.data.categories.length > 0 && (
        <ul className="plates">
          {filters.data.categories.map((category) => {
            const Icon = categoryIcon(category.name)
            return (
              <li key={category.name}>
                <Link className="plate-link" to={`/schemes?category=${encodeURIComponent(category.name)}`}>
                  <Icon size={28} strokeWidth={2} aria-hidden="true" />
                  <span>
                    <span className="plate-link__name">{category.name}</span>
                    <br />
                    <span className="plate-link__count num">
                      {category.count} {category.count === 1 ? 'scheme' : 'schemes'}
                    </span>
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}

      {filters.data?.needs?.length > 0 && (
        <>
          <h2 className="section-title">Schemes for people like you</h2>
          <ul className="chips">
            {filters.data.needs.map((need) => (
              <li key={need.key}>
                <Link className="chip" to={`/schemes?need=${need.key}`}>
                  {need.label}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
