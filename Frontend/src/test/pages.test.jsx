/* MOCK / TEST ONLY: every API response below is an invented fixture served by a stubbed fetch. */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { NOT_AVAILABLE } from '../components.jsx'
import { CompareProvider } from '../compare.jsx'
import EligibilityPage from '../pages/EligibilityPage.jsx'
import SchemePage from '../pages/SchemePage.jsx'
import SearchPage from '../pages/SearchPage.jsx'

function stubApi(routes) {
  const calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, init = {}) => {
      const path = String(url)
      calls.push({ path, method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body) : undefined })
      const match = routes.find(([method, prefix]) => (init.method ?? 'GET') === method && path.startsWith(prefix))
      if (!match) return new Response(JSON.stringify({ detail: 'not found' }), { status: 404 })
      const [, , status, body] = match
      return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
    }),
  )
  return calls
}

function renderAt(path, routePath, element) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CompareProvider>
        <Routes>
          <Route path={routePath} element={element} />
        </Routes>
      </CompareProvider>
    </MemoryRouter>,
  )
}

const FILTERS = {
  categories: [],
  states: ['Bihar', 'Kerala'],
  genders: ['Male', 'Female', 'Transgender'],
  occupations: [],
  beneficiaryTypes: [],
  needs: [],
  levels: ['Central', 'State'],
}

describe('eligibility question flow', () => {
  it('asks one question at a time, sends answers in one call and shows reasons with the notice', async () => {
    const user = userEvent.setup()
    const calls = stubApi([
      ['GET', '/api/filters', 200, FILTERS],
      [
        'POST',
        '/api/eligibility/check',
        200,
        {
          likelyMatch: 1,
          moreInfoNeeded: 0,
          notAMatch: 3,
          results: [
            {
              schemeId: 'test-bihar',
              name: 'Test Bihar Support',
              description: 'Fixture scheme.',
              sourceUrl: 'https://www.myscheme.gov.in/schemes/test-bihar',
              status: 'LIKELY_MATCH',
              matched: [{ field: 'state', requirement: 'State: Bihar', yourValue: 'Bihar' }],
              unmatched: [],
              missing: [],
            },
          ],
        },
      ],
    ])
    renderAt('/eligibility', '/eligibility', <EligibilityPage />)

    await user.type(await screen.findByLabelText('How old are you?'), '25')
    await user.click(screen.getByRole('button', { name: /Next/ }))
    await user.selectOptions(screen.getByLabelText('Which state or union territory do you live in?'), 'Bihar')
    await user.click(screen.getByRole('button', { name: /Next/ }))
    await user.click(screen.getByRole('button', { name: 'Skip this question' })) // gender
    await user.click(screen.getByRole('button', { name: 'Skip this question' })) // social category

    const income = screen.getByLabelText("What is your family's total income in a year?")
    await user.type(income, 'abc')
    await user.click(screen.getByRole('button', { name: /See my results/ }))
    expect(screen.getByText('Enter the amount in rupees as a whole number.')).toBeTruthy()
    await user.clear(income)
    await user.type(income, '1,50,000')
    await user.click(screen.getByRole('button', { name: /See my results/ }))

    expect(await screen.findByRole('link', { name: 'Test Bihar Support' })).toBeTruthy()
    const check = calls.filter((c) => c.path.startsWith('/api/eligibility/check'))
    expect(check).toHaveLength(1)
    expect(check[0].body).toEqual({ age: 25, state: 'Bihar', annualIncome: 150000 })
    expect(screen.getByText('This is guidance only, not a decision.')).toBeTruthy()
    expect(screen.getByText('Likely match')).toBeTruthy()
    expect(screen.getByText('Conditions you meet')).toBeTruthy()
    expect(screen.getByText(/State: Bihar/)).toBeTruthy()
  })
})

const SCHEME = {
  id: 'test-scheme',
  name: 'Test Pension Scheme',
  description: 'A test pension.',
  eligibilityText: 'Applicant must be 60 or older.',
  benefits: 'Rs 1000 per month.',
  documents: null,
  applicationProcess: 'Apply online.',
  conditions: null,
  level: 'Central',
  state: null,
  categories: ['Social welfare & Empowerment'],
  faqs: [],
  references: [],
  sourceUrl: 'https://www.myscheme.gov.in/schemes/test-scheme',
  sourceName: 'myScheme',
  syncedAt: '2026-09-27T10:00:00Z',
}

describe('scheme detail', () => {
  it('shows missing fields honestly and keeps the official text beside the simple version', async () => {
    const user = userEvent.setup()
    stubApi([
      ['GET', '/api/schemes/test-scheme/related', 200, { items: [], available: false }],
      ['GET', '/api/schemes/test-scheme', 200, SCHEME],
      ['POST', '/api/schemes/test-scheme/explain', 200, { section: 'eligibilityText', original: SCHEME.eligibilityText, explanation: 'You must be 60 or older.' }],
    ])
    renderAt('/schemes/test-scheme', '/schemes/:id', <SchemePage />)

    const documents = (await screen.findByRole('heading', { name: 'Documents required' })).closest('section')
    expect(within(documents).getByText(NOT_AVAILABLE)).toBeTruthy()
    expect(within(documents).queryByRole('button', { name: /Explain simply/ })).toBeNull()

    const eligibility = screen.getByRole('heading', { name: 'Who can apply' }).closest('section')
    await user.click(within(eligibility).getByRole('button', { name: /Explain simply/ }))
    expect(await within(eligibility).findByText('You must be 60 or older.')).toBeTruthy()
    expect(within(eligibility).getByText('Applicant must be 60 or older.')).toBeTruthy()
    expect(within(eligibility).getByText(/written by AI from the official text/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Open official page/ }).getAttribute('href')).toBe(SCHEME.sourceUrl)
  })
})

describe('search', () => {
  it('tells the user when only exact word matches are available', async () => {
    stubApi([
      [
        'GET',
        '/api/search',
        200,
        {
          items: [{ scheme: { ...SCHEME }, matchedByKeyword: true, matchedByMeaning: false }],
          page: 0,
          size: 20,
          total: 1,
          semanticAvailable: false,
        },
      ],
    ])
    renderAt('/search?q=pension', '/search', <SearchPage />)
    expect(await screen.findByText(/Showing exact word matches only/)).toBeTruthy()
    expect(screen.getByText('Matches your words')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Test Pension Scheme' }).getAttribute('href')).toBe('/schemes/test-scheme')
  })
})
