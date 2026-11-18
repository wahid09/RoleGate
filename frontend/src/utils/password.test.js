import { describe, expect, it } from 'vitest'
import { passwordStrength } from './password'

describe('passwordStrength', () => {
  it('is empty for no input', () => expect(passwordStrength('')).toEqual({ score: 0, label: '' }))
  it('caps short passwords at weak', () => expect(passwordStrength('Ab1!').score).toBeLessThanOrEqual(1))
  it('rates longer mixed passwords higher', () => {
    expect(passwordStrength('correct horse battery 9!').score).toBe(4)
    expect(passwordStrength('abcdefgh').score).toBeLessThan(passwordStrength('Abcdefgh12!x').score)
  })
})
