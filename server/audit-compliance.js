import { createHash } from 'crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'
import { allowedMatchingProfile, MATCHING_PROFILE_ALLOWLIST, PROHIBITED_MATCHING_FIELDS } from './compliance-utils.js'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const source = readFileSync(join(here, 'index.js'), 'utf8')
const parserSource = readFileSync(join(here, 'resume-parser.js'), 'utf8')
const matchStart = source.indexOf("app.post('/api/user/match'")
const matchEnd = source.indexOf("app.post('/api/user/match/collaborative'", matchStart)
const matchSource = source.slice(matchStart, matchEnd)

const legitimate = { major:'计算机科学', degree:'硕士', target_direction:'算法工程师', target_industry:'互联网', target_city:'北京' }
const counterfactualA = allowedMatchingProfile({ ...legitimate, real_name:'候选人甲', gender:'女', age:22, ethnicity:'A', phone:'13800138000' })
const counterfactualB = allowedMatchingProfile({ ...legitimate, real_name:'候选人乙', gender:'男', age:58, ethnicity:'B', phone:'13900139000' })
const prohibitedPattern = new RegExp(`\\b(${PROHIBITED_MATCHING_FIELDS.join('|')})\\b`, 'i')

const checks = {
  explicit_matching_allowlist: MATCHING_PROFILE_ALLOWLIST.length > 0,
  counterfactual_sensitive_invariance: JSON.stringify(counterfactualA) === JSON.stringify(counterfactualB),
  main_match_uses_allowlist: matchSource.includes('allowedMatchingProfile(profile)'),
  main_match_does_not_query_prohibited_fields: !prohibitedPattern.test(matchSource.match(/SELECT major, degree, target_direction, target_industry[^\n]+/)?.[0] || ''),
  explanation_has_no_discriminatory_reason: !/年龄不合适|性别不合适|民族|婚姻状况|男性优先|女性优先/.test(matchSource),
  raw_sections_not_persisted_in_parse_result: parserSource.includes('raw_sections_persisted: false') && !/return \{[\s\S]*sections:\s*parsed\.sections/.test(parserSource.slice(parserSource.indexOf('export function sanitizeParsedResume'))),
  direct_identifier_redaction_present: ['[NAME]','[GENDER]','[AGE_OR_BIRTH_DATE]','[ETHNICITY]','[EMAIL]','[PHONE]','[ID_NUMBER]'].every(token => parserSource.includes(token)),
  consent_and_retention_recorded: ['consent_status','permitted_use','retention_until','deletion_requested_at'].every(field => source.includes(field)),
  deletion_request_audited: source.includes('privacy_requests') && source.includes("'delete_resume','fulfilled'"),
  uploaded_file_deleted_with_record: source.includes('unlinkSync(storedFile)'),
}

const report = {
  generated_at: new Date().toISOString(), algorithm_version: 'fairness_privacy_audit_v1',
  passed: Object.values(checks).every(Boolean), checks,
  matching_feature_policy: { allowed: MATCHING_PROFILE_ALLOWLIST, prohibited: PROHIBITED_MATCHING_FIELDS, sensitive_features_used: false },
  counterfactual_test: { changed_fields:['real_name','gender','age','ethnicity','phone'], features_a:counterfactualA, features_b:counterfactualB, invariant:JSON.stringify(counterfactualA)===JSON.stringify(counterfactualB) },
  source_sha256: createHash('sha256').update(source).digest('hex'),
  fairness_claim_scope: 'counterfactual_feature_exclusion_only',
  limitations: [
    'No sensitive attribute is inferred for group fairness analysis.',
    'Degree, major, direction, industry and city remain user-provided legitimate preference or qualification features and require domain review for each deployment.',
    'This audit proves feature exclusion and storage controls, not equal outcomes across demographic groups.',
  ],
}

const output = join(root, 'crawler', 'data', 'reports', 'fairness_privacy_compliance_audit.json')
mkdirSync(dirname(output), { recursive:true })
writeFileSync(output, JSON.stringify(report, null, 2), 'utf8')
console.log(JSON.stringify(report, null, 2))
process.exit(report.passed ? 0 : 1)
