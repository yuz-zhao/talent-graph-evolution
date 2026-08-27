import pg from 'pg'

pg.types.setTypeParser(20, value => Number(value))
pg.types.setTypeParser(1700, value => Number(value))

function replacePlaceholders(sql) {
  let index = 0
  let quote = null
  let output = ''
  for (let i = 0; i < sql.length; i++) {
    const char = sql[i]
    if (quote) {
      output += char
      if (char === quote && sql[i - 1] !== '\\') quote = null
      continue
    }
    if (char === "'" || char === '"') {
      quote = char
      output += char
    } else if (char === '?') {
      output += `$${++index}`
    } else {
      output += char
    }
  }
  return output
}

function translateUpsert(sql) {
  const match = sql.match(/\s+ON DUPLICATE KEY UPDATE\s+([\s\S]+)$/i)
  if (!match) return sql
  const table = sql.match(/^\s*INSERT\s+INTO\s+([a-z_]+)/i)?.[1]?.toLowerCase()
  const conflictKeys = {
    user_profiles: 'user_id',
    user_job_actions: 'user_id, job_id',
  }
  const key = conflictKeys[table]
  if (!key) throw new Error(`PostgreSQL compatibility: missing conflict key for ${table}`)
  const updates = match[1].replace(/([a-z_]+)\s*=\s*VALUES\(\1\)/gi, '$1=EXCLUDED.$1')
  return sql.slice(0, match.index) + ` ON CONFLICT (${key}) DO UPDATE SET ${updates}`
}

function translateSql(input) {
  let sql = input.trim().replace(/`/g, '"')
  sql = translateUpsert(sql)
  sql = sql.replace(
    /completed_at\s*=\s*IF\(is_completed,\s*NULL,\s*NOW\(\)\)/gi,
    'completed_at=CASE WHEN is_completed=1 THEN NULL ELSE NOW() END',
  )
  sql = sql.replace(
    /is_completed\s*=\s*NOT\s+is_completed/gi,
    'is_completed=CASE WHEN is_completed=1 THEN 0 ELSE 1 END',
  )
  sql = sql.replace(
    /completed_at\s*=\s*IF\(\?\s*=\s*1,\s*NOW\(\),\s*NULL\)/gi,
    'completed_at=CASE WHEN ?=1 THEN NOW() ELSE NULL END',
  )
  sql = sql.replace(/DATE_FORMAT\(([^,]+),\s*'%Y-%m-%d'\)/gi, "TO_CHAR($1, 'YYYY-MM-DD')")
  sql = sql.replace(/\bTINYINT\s*\(\s*1\s*\)/gi, 'smallint')
  return replacePlaceholders(sql)
}

function isSelect(sql) {
  return /^\s*(SELECT|WITH|SHOW)\b/i.test(sql)
}

function expandBulkValues(sql, params) {
  if (!/\bVALUES\s+\?/i.test(sql) || params.length !== 1 || !Array.isArray(params[0])) {
    return { sql, params }
  }
  const rows = params[0]
  if (!rows.length) throw new Error('PostgreSQL compatibility: empty bulk insert')
  const width = rows[0].length
  if (!width || rows.some(row => !Array.isArray(row) || row.length !== width)) {
    throw new Error('PostgreSQL compatibility: inconsistent bulk insert rows')
  }
  const groups = rows.map(() => `(${Array(width).fill('?').join(',')})`).join(',')
  return {
    sql: sql.replace(/\bVALUES\s+\?/i, `VALUES ${groups}`),
    params: rows.flat(),
  }
}

export function createPostgresCompatPool(config) {
  const client = new pg.Pool({
    ...config,
    max: config.connectionLimit || 10,
    options: config.options || '-c search_path=legacy_app,app,core,ingest,ops,public',
  })

  async function run(rawSql, params = []) {
    const expanded = expandBulkValues(rawSql, params)
    let sql = translateSql(expanded.sql)
    const insert = /^\s*INSERT\s+INTO\s+/i.test(sql)
    if (insert && !/\bRETURNING\b/i.test(sql)) sql += ' RETURNING id'
    const result = await client.query(sql, expanded.params)
    if (isSelect(sql)) return [result.rows, result.fields]
    const packet = {
      affectedRows: result.rowCount,
      insertId: insert ? result.rows[0]?.id ?? null : null,
      changedRows: result.rowCount,
    }
    return [packet, result.fields]
  }

  return {
    execute: run,
    query: run,
    end: () => client.end(),
    raw: client,
  }
}

export { translateSql }
