// Initials and a stable colour for a user, so the same person always gets the same avatar.
export function initials(name, email = '') {
  const words = (name || '').trim().split(/\s+/).filter(Boolean)
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase()
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (email.trim()[0] || '?').toUpperCase()
}

export function hueFor(seed = '') {
  let h = 0
  for (const ch of seed.toLowerCase()) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return h % 360
}
