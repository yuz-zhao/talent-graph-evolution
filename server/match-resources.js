/**
 * Filesystem loader for the matching feature layer.
 *
 * match-features.js stays pure so it can be unit tested and reused from the API
 * process; this module is the only place that touches disk. Everything it reads
 * is a committed artifact, so evaluation runs offline -- no Neo4j, no network.
 *
 * Prerequisite: node crawler/scripts/build_skill_document_frequency.mjs
 */
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseCsvRecords } from './csv-parse.js'
import { buildFeatureResources } from './match-features.js'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

export const RESOURCE_PATHS = Object.freeze({
  ontology: join(root, 'crawler', 'data', 'gold', 'reference', 'skill_ontology.json'),
  documentFrequency: join(root, 'crawler', 'data', 'reference', 'skill_document_frequency.json'),
  jobStandardDict: join(root, 'crawler', 'data', 'gold', 'reference', 'job_standard_dict.csv'),
})

function readJson(path, hint) {
  if (!existsSync(path)) throw new Error(`缺少 ${path}${hint ? `\n  ${hint}` : ''}`)
  return JSON.parse(readFileSync(path, 'utf8'))
}

let cached = null

/** Loads and caches the shared lookup tables. Pass { fresh: true } to bypass the cache. */
export function loadMatchResources({ fresh = false } = {}) {
  if (cached && !fresh) return cached
  const ontology = readJson(RESOURCE_PATHS.ontology)
  const frequency = readJson(
    RESOURCE_PATHS.documentFrequency,
    '先跑 node crawler/scripts/build_skill_document_frequency.mjs',
  )
  const jobFamilyRows = existsSync(RESOURCE_PATHS.jobStandardDict)
    ? parseCsvRecords(readFileSync(RESOURCE_PATHS.jobStandardDict, 'utf8'))
    : []
  cached = buildFeatureResources({
    ontology,
    documentFrequency: frequency.documentFrequency,
    totalJobs: frequency.totalJobs,
    jobFamilyRows,
  })
  return cached
}
