const LEVEL_TERMS = {
  junior: ['初级', '助理', 'junior', 'intern', '实习'],
  mid: ['中级', '资深', 'senior'],
  senior: ['高级', '资深', 'senior', '专家', '架构师', '负责人', 'lead', 'principal'],
}

export function normalizeGraphFilters(query = {}) {
  const level = String(query.level || '').trim().toLowerCase()
  return {
    techStack: String(query.tech_stack || '').trim(),
    level: Object.hasOwn(LEVEL_TERMS, level) ? level : '',
  }
}

export function buildGraphFilteredNodeQuery(filters, limit = 500) {
  const safeLimit = Math.min(Math.max(Number(limit) || 500, 1), 3000)
  const terms = LEVEL_TERMS[filters.level] || []
  const levelClause = terms.length
    ? 'AND any(term IN $levelTerms WHERE toLower(coalesce(j.standard_name, j.title, "")) CONTAINS term)'
    : ''
  const stackClause = filters.techStack
    ? 'AND any(sk IN skills WHERE toLower(sk.name) CONTAINS toLower($techStack))'
    : ''
  return {
    cypher: `MATCH (j:岗位) OPTIONAL MATCH (j)-[:要求技能]->(skill:技能)
      WITH j, collect(DISTINCT skill) AS skills
      WHERE true ${levelClause} ${stackClause}
      WITH collect(j) + reduce(all = [], sks IN collect(skills) | all + sks) AS selected
      UNWIND selected AS n WITH DISTINCT n WHERE n IS NOT NULL
      OPTIONAL MATCH (n)-[rel]-()
      RETURN ID(n) AS id, labels(n)[0] AS label,
      CASE labels(n)[0] WHEN "岗位" THEN coalesce(n.standard_name,n.title) WHEN "技能" THEN n.name END AS name,
      count(rel) AS degree ORDER BY degree DESC LIMIT ${safeLimit}`,
    params: { techStack: filters.techStack, levelTerms: terms },
    strategy: 'neo4j_job_skill_relationship_and_title_level',
  }
}
