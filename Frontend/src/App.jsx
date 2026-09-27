import { useEffect } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router'
import { ErrorBoundary } from './components.jsx'
import { useCompare } from './compare.jsx'
import AskPage from './pages/AskPage.jsx'
import BrowsePage from './pages/BrowsePage.jsx'
import ComparePage from './pages/ComparePage.jsx'
import EligibilityPage from './pages/EligibilityPage.jsx'
import HomePage from './pages/HomePage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import SchemePage from './pages/SchemePage.jsx'
import SearchPage from './pages/SearchPage.jsx'

export default function App() {
  const { pathname } = useLocation()
  const compare = useCompare()

  // A new page starts at the top, like a new notice.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="wrap site-header__inner">
          <NavLink to="/" className="wordmark" aria-label="YojnaSetu home">
            <span className="wordmark__name lettering">
              Yojna<span>Setu</span>
            </span>
            <span className="wordmark__tag">Scheme finder · guidance only</span>
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/schemes">Browse</NavLink>
            <NavLink to="/eligibility">Eligibility</NavLink>
            <NavLink to="/ask">Ask</NavLink>
            <NavLink to="/compare">
              Compare
              {compare.ids.length > 0 && (
                <span className="nav__count num" aria-label={`${compare.ids.length} selected`}>
                  {compare.ids.length}
                </span>
              )}
            </NavLink>
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1}>
        <ErrorBoundary key={pathname}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/schemes" element={<BrowsePage />} />
            <Route path="/schemes/:id" element={<SchemePage />} />
            <Route path="/eligibility" element={<EligibilityPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/ask" element={<AskPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
      </main>

      <footer className="site-footer">
        <div className="wrap site-footer__inner">
          <p>
            <strong>YojnaSetu gives guidance only.</strong> It does not process applications or decide
            eligibility; the concerned government department makes the final decision.
          </p>
          <p>
            Scheme information comes only from official Government of India sources: the myScheme platform
            (MeitY, via API Setu) and the Open Government Data Platform (data.gov.in). Every scheme links to its
            official page. YojnaSetu is an independent tool, not a government website.
          </p>
        </div>
      </footer>
    </>
  )
}
