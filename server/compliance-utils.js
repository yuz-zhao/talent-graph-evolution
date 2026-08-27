export const MATCHING_PROFILE_ALLOWLIST = Object.freeze([
  'major', 'degree', 'target_direction', 'target_industry', 'target_city',
])

export const PROHIBITED_MATCHING_FIELDS = Object.freeze([
  'real_name', 'name', 'gender', 'sex', 'age', 'birthday', 'birth_date',
  'ethnicity', 'nation', 'marital_status', 'phone', 'email', 'id_number',
])

export function allowedMatchingProfile(profile = {}) {
  return Object.fromEntries(MATCHING_PROFILE_ALLOWLIST.map(field => [field, String(profile?.[field] || '').trim()]))
}

export function matchingFeatureAudit(profile = {}) {
  const allowed = allowedMatchingProfile(profile)
  const rejected = PROHIBITED_MATCHING_FIELDS.filter(field => profile?.[field] !== undefined && profile?.[field] !== null && profile?.[field] !== '')
  return { allowed, rejected, sensitive_features_used: false, policy_version: 'matching_feature_policy_v1' }
}
