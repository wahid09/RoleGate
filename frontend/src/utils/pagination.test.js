import { describe, expect, it } from 'vitest'
import { pageWindow, rangeLabel } from './pagination'

describe('pageWindow', () => {
  it('shows every page when there are few', () => {
    expect(pageWindow(1, 1)).toEqual([1])
    expect(pageWindow(2, 3)).toEqual([1, 2, 3])
  })
  it('collapses long runs into ellipses', () => {
    expect(pageWindow(1, 20)).toEqual([1, 2, null, 20])
    expect(pageWindow(7, 20)).toEqual([1, null, 6, 7, 8, null, 20])
    expect(pageWindow(20, 20)).toEqual([1, null, 19, 20])
  })
  it('does not hide a single page behind an ellipsis', () => {
    expect(pageWindow(4, 8)).toEqual([1, 2, 3, 4, 5, null, 8])
  })
})

describe('rangeLabel', () => {
  it('describes the visible rows', () => {
    expect(rangeLabel(1, 10, 0)).toBe('No results')
    expect(rangeLabel(1, 10, 6)).toBe('Showing 1–6 of 6')
    expect(rangeLabel(3, 10, 25)).toBe('Showing 21–25 of 25')
  })
})
