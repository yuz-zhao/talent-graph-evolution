/** Distance-weighted k-nearest-neighbour classifier for small human-gold sets. */
export function trainKnn(rows, { k = 25, distanceFloor = 0.05 } = {}) {
  if (!rows.length) throw new Error('KNN training rows are required')
  const dimension = rows[0].x.length
  const mean = Array(dimension).fill(0)
  const deviation = Array(dimension).fill(0)
  for (const row of rows) row.x.forEach((value, i) => { mean[i] += value / rows.length })
  for (const row of rows) row.x.forEach((value, i) => { deviation[i] += (value - mean[i]) ** 2 / rows.length })
  for (let i = 0; i < dimension; i++) deviation[i] = Math.sqrt(deviation[i]) || 1
  const prepared = rows.map(row => ({
    y: Number(row.y),
    x: row.x.map((value, i) => (value - mean[i]) / deviation[i]),
  }))

  const votes = x => {
    const normalized = x.map((value, i) => (value - mean[i]) / deviation[i])
    const nearest = prepared.map(row => ({
      y: row.y,
      distance: Math.sqrt(normalized.reduce((sum, value, i) => sum + (value - row.x[i]) ** 2, 0)),
    })).sort((a, b) => a.distance - b.distance).slice(0, Math.min(k, prepared.length))
    const totals = [0, 0, 0, 0]
    for (const item of nearest) totals[item.y] += 1 / (item.distance + distanceFloor)
    return totals
  }

  return {
    k, mean, deviation,
    probabilities(x) {
      const totals = votes(x), total = totals.reduce((a, b) => a + b, 0) || 1
      return totals.map(value => value / total)
    },
    predict(x) {
      const totals = votes(x)
      return totals.indexOf(Math.max(...totals))
    },
  }
}
