import { describe, expect, it } from 'vitest'
import { hueFor, initials } from './avatar'

describe('initials', () => {
  it('uses first and second word', () => {
    expect(initials('Ada Lovelace')).toBe('AL')
    expect(initials('  grace   brewster   hopper ')).toBe('GB')
  })
  it('falls back to one word, then the email', () => {
    expect(initials('Cher')).toBe('CH')
    expect(initials('', 'zed@example.com')).toBe('Z')
    expect(initials('', '')).toBe('?')
  })
})

describe('hueFor', () => {
  it('is stable, case-insensitive and within 0-359', () => {
    expect(hueFor('Ada@Example.com')).toBe(hueFor('ada@example.com'))
    for (const s of ['a', 'b@c.d', 'a much longer seed value']) {
      const h = hueFor(s)
      expect(h).toBeGreaterThanOrEqual(0)
      expect(h).toBeLessThan(360)
    }
  })
  it('spreads different people across different colours', () => {
    const hues = new Set(['a@x.io', 'b@x.io', 'c@x.io', 'd@x.io', 'e@x.io'].map(hueFor))
    expect(hues.size).toBeGreaterThan(3)
  })
})
