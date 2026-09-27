import { describe, expect, it } from 'vitest'
import { buildQuestions, describeAnswer, toProfile, validateAnswer } from '../eligibility.js'

const FILTERS = { states: ['Bihar'], genders: ['Male', 'Female'], occupations: [] }

describe('eligibility helpers', () => {
  it('asks about occupation only when stored conditions name occupations', () => {
    expect(buildQuestions(FILTERS).map((q) => q.key)).toEqual(['age', 'state', 'gender', 'socialCategory', 'annualIncome'])
    expect(buildQuestions({ ...FILTERS, occupations: ['Farmer'] }).map((q) => q.key)).toContain('occupation')
  })

  it('sends only answered questions, with numbers as numbers', () => {
    expect(toProfile({ age: '25', state: 'Bihar', gender: '', annualIncome: '150000' })).toEqual({
      age: 25,
      state: 'Bihar',
      annualIncome: 150000,
    })
  })

  it('rejects empty and malformed answers with a helpful message', () => {
    const [age] = buildQuestions(FILTERS)
    expect(validateAnswer(age, '')).toMatch(/skip this question/)
    expect(validateAnswer(age, '121')).toMatch(/0 to 120/)
    expect(validateAnswer(age, '2.5')).toMatch(/whole number/)
    expect(validateAnswer(age, '40')).toBe('')
  })

  it('describes answers in plain words with Indian digit grouping', () => {
    const questions = buildQuestions(FILTERS)
    expect(describeAnswer(questions.at(-1), '250000')).toBe('₹2,50,000 a year')
    expect(describeAnswer(questions[3], 'SC')).toBe('Scheduled Caste (SC)')
  })
})
