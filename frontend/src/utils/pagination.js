// Page numbers to show, with null standing for an ellipsis: pageWindow(7, 20) -> [1, null, 6, 7, 8, null, 20]
export function pageWindow(current, total, around = 1) {
  if (total <= 1) return [1]
  const pages = new Set([1, total])
  for (let p = current - around; p <= current + around; p++) if (p > 1 && p < total) pages.add(p)
  const sorted = [...pages].sort((a, b) => a - b)
  const out = []
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push(sorted[i - 1] + 1 === p - 1 ? sorted[i - 1] + 1 : null)
    out.push(p)
  })
  return out
}

export function rangeLabel(page, pageSize, total) {
  if (!total) return 'No results'
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)
  return `Showing ${from}–${to} of ${total}`
}
