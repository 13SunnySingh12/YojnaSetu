/* MOCK / TEST ONLY: the filters response is an invented fixture served by a stubbed fetch. */
import { render, screen } from '@testing-library/react'
import { StrictMode } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import App from '../App.jsx'
import { CompareProvider } from '../compare.jsx'

describe('app shell', () => {
  it('renders when window.scrollTo returns a promise, as it does in current browsers', async () => {
    // Found in a live browser: an effect that implicitly returned scrollTo's promise crashed the app.
    vi.stubGlobal('scrollTo', vi.fn(() => Promise.resolve()))
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({ categories: [], states: [], genders: [], occupations: [], beneficiaryTypes: [], needs: [], levels: [] }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    render(
      <StrictMode>
        <MemoryRouter>
          <CompareProvider>
            <App />
          </CompareProvider>
        </MemoryRouter>
      </StrictMode>,
    )
    expect(await screen.findByRole('heading', { name: 'Find government schemes that fit you' })).toBeTruthy()
    expect(await screen.findByText('No schemes are loaded yet')).toBeTruthy()
    expect(window.scrollTo).toHaveBeenCalled()
  })
})
