import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(fileURLToPath(import.meta.url))
const importDir = join(root, 'import')
const contract = JSON.parse(readFileSync(join(root, 'graph_schema.json'), 'utf8'))
const checks = {}
const counts = {}
const errors = []

function parseCsvLine(line) {
  const cells = []
  let value = ''
  let quoted = false
  for (let i = 0; i < line.length; i++) {
    const char = line[i]
    if (char === '"') {
      if (quoted && line[i + 1] === '"') { value += '"'; i++ }
      else quoted = !quoted
    } else if (char === ',' && !quoted) {
      cells.push(value)
      value = ''
    } else value += char
  }
  cells.push(value)
  return cells
}

for (const [filename, required] of Object.entries(contract.required_files)) {
  const path = join(importDir, filename)
  const exists = existsSync(path)
  checks[`exists:${filename}`] = exists
  if (!exists) {
    errors.push(`missing file: ${filename}`)
    continue
  }
  const lines = readFileSync(path, 'utf8').replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean)
  const header = parseCsvLine(lines[0] || '')
  const count = Math.max(lines.length - 1, 0)
  counts[filename] = count
  const missing = required.filter(column => !header.includes(column))
  checks[`columns:${filename}`] = missing.length === 0
  checks[`nonempty:${filename}`] = count > 0
  if (missing.length) errors.push(`${filename} missing columns: ${missing.join(', ')}`)
  if (!count) errors.push(`empty file: ${filename}`)
}

const result = {
  contract_version: contract.version,
  passed: errors.length === 0,
  checks,
  counts,
  errors,
}
writeFileSync(join(importDir, 'graph_contract_report.json'), JSON.stringify(result, null, 2), 'utf8')
console.log(JSON.stringify(result, null, 2))
if (!result.passed) process.exitCode = 1
