import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GuidanceNotice, NOT_AVAILABLE, OfficialText, StatusPlate } from '../components.jsx'

describe('OfficialText', () => {
  it('says plainly when the official source did not provide the text', () => {
    render(
      <>
        <OfficialText text={null} />
        <OfficialText text="   " />
      </>,
    )
    expect(screen.getAllByText(NOT_AVAILABLE)).toHaveLength(2)
  })

  it('keeps the wording, renders bold and links only web addresses', () => {
    const { container } = render(
      <OfficialText text={'1. Be a **resident**.\nApply at https://example.gov.in/apply. javascript:alert(1)'} />,
    )
    expect(container.querySelector('strong').textContent).toBe('resident')
    const links = container.querySelectorAll('a')
    expect(links).toHaveLength(1)
    expect(links[0].getAttribute('href')).toBe('https://example.gov.in/apply')
    expect(links[0].getAttribute('rel')).toBe('noopener noreferrer')
    expect(container.textContent).toContain('javascript:alert(1)')
  })
})

describe('result labels', () => {
  it('names every status in words, never by colour alone', () => {
    render(
      <>
        <StatusPlate status="LIKELY_MATCH" />
        <StatusPlate status="NOT_A_MATCH" />
        <StatusPlate status="MORE_INFO_NEEDED" />
      </>,
    )
    expect(screen.getByText('Likely match')).toBeTruthy()
    expect(screen.getByText('Not a match')).toBeTruthy()
    expect(screen.getByText('More information needed')).toBeTruthy()
  })

  it('shows the fixed guidance notice', () => {
    render(<GuidanceNotice />)
    expect(screen.getByText('This is guidance only, not a decision.')).toBeTruthy()
    expect(screen.getByText(/concerned government department makes the final decision/)).toBeTruthy()
  })
})
