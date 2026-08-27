/** Minimal RFC4180 CSV reader: quoted fields, escaped quotes, embedded newlines, BOM. */
export function parseCsv(text) {
  const rows = []
  let row = [], cell = '', quoted = false
  const body = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text
  for (let i = 0; i < body.length; i++) {
    const char = body[i]
    if (quoted) {
      if (char !== '"') cell += char
      else if (body[i + 1] === '"') { cell += '"'; i++ }
      else quoted = false
      continue
    }
    if (char === '"') quoted = true
    else if (char === ',') { row.push(cell); cell = '' }
    else if (char === '\n') { row.push(cell); rows.push(row); row = []; cell = '' }
    else if (char !== '\r') cell += char
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row) }
  return rows
}

/** Same as parseCsv but returns objects keyed by the header row. */
export function parseCsvRecords(text) {
  const rows = parseCsv(text).filter(row => row.length > 1)
  if (!rows.length) return []
  const header = rows[0]
  return rows.slice(1).map(cells => Object.fromEntries(header.map((key, index) => [key, cells[index] ?? ''])))
}
