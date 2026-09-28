const SOCIAL_CATEGORIES = [
  ['General', 'General'],
  ['OBC', 'Other Backward Class (OBC)'],
  ['SC', 'Scheduled Caste (SC)'],
  ['ST', 'Scheduled Tribe (ST)'],
]

/** The question flow. Occupation is asked only when stored conditions actually name occupations. */
export function buildQuestions(filters) {
  const questions = [
    {
      key: 'age',
      title: 'How old are you?',
      hint: 'Many schemes have an age limit. Enter your age in years.',
      kind: 'number',
      max: 120,
    },
    {
      key: 'state',
      title: 'Which state or union territory do you live in?',
      hint: 'Many schemes are only for people who live in a particular state.',
      kind: 'select',
      options: filters.states.map((s) => [s, s]),
    },
    {
      key: 'gender',
      title: 'What is your gender?',
      hint: 'Some schemes are meant only for women, men or transgender persons.',
      kind: 'choice',
      options: filters.genders.map((g) => [g, g]),
    },
    {
      key: 'socialCategory',
      title: 'Which social category do you belong to?',
      hint: 'Some schemes are meant for a particular social category, such as SC or ST.',
      kind: 'choice',
      options: SOCIAL_CATEGORIES,
    },
  ]
  if (filters.occupations?.length) {
    questions.push({
      key: 'occupation',
      title: 'What is your main occupation?',
      hint: 'Some schemes are only for certain kinds of work, such as farming.',
      kind: 'select',
      options: filters.occupations.map((o) => [o, o]),
    })
  }
  questions.push({
    key: 'annualIncome',
    title: "What is your family's total income in a year?",
    hint: 'Many schemes have an income limit. Add up the yearly income of all family members, in rupees. An estimate is fine.',
    kind: 'number',
    max: 1_000_000_000,
  })
  return questions
}

/** Only answered questions are sent; unanswered ones become "information not provided". */
export function toProfile(answers) {
  const profile = {}
  Object.entries(answers).forEach(([key, value]) => {
    if (value === '' || value === undefined) return
    profile[key] = key === 'age' || key === 'annualIncome' ? Number(value) : value
  })
  return profile
}

/** Returns an error message, or '' when the answer is acceptable. */
export function validateAnswer(question, value) {
  if (value === '' || value === undefined) return 'Choose an answer, or skip this question.'
  if (question.kind === 'number' && !(/^\d+$/.test(value) && Number(value) <= question.max)) {
    return question.key === 'age'
      ? 'Enter your age as a whole number from 0 to 120.'
      : 'Enter the amount in rupees as a whole number.'
  }
  return ''
}

export function describeAnswer(question, value) {
  if (question.key === 'annualIncome') return `₹${Number(value).toLocaleString('en-IN')} a year`
  if (question.key === 'age') return `${value} years`
  return question.options?.find(([v]) => v === value)?.[1] ?? value
}
