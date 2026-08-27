/**
 * Proportional-odds cumulative-link model for the ordinal 0-3 relevance label.
 *
 * The previous classifier was a 4-class softmax with balanced class weights. On
 * the frozen test it predicted class 3 for 101 of 400 pairs -- 25.25%, i.e. exactly
 * the uniform class prior that balanced weighting optimises for -- while only 73
 * were truly class 3. With just 5 class-3 training examples carrying a 10x weight,
 * the model degenerated into emitting the flat prior. CV said 66%, the test said
 * 47.25%.
 *
 * This model instead shares one coefficient vector across all cut points and
 * learns three ordered thresholds:
 *
 *     P(y >= k) = sigmoid(w·x - theta_k),   theta_1 < theta_2 < theta_3
 *
 * Ordering is structural, not a post-hoc repair: theta is parameterised as
 * (t1, t1+exp(g1), t1+exp(g1)+exp(g2)). That is ~22 parameters instead of 4x22,
 * it cannot invert the tiers, and adjacent confusions -- 106 of the 138 rule-based
 * errors -- are what an ordinal likelihood is built to penalise proportionally.
 */

const sigmoid = z => 1 / (1 + Math.exp(-z))
const EPSILON = 1e-9

/** theta_1 < theta_2 < theta_3 by construction. */
function thresholds(raw) {
  const [first, gap1, gap2] = raw
  const second = first + Math.exp(gap1)
  return [first, second, second + Math.exp(gap2)]
}

function standardize(rows) {
  const dimension = rows[0].x.length
  const mean = Array(dimension).fill(0)
  const deviation = Array(dimension).fill(0)
  for (const row of rows) row.x.forEach((value, i) => { mean[i] += value / rows.length })
  for (const row of rows) row.x.forEach((value, i) => { deviation[i] += (value - mean[i]) ** 2 / rows.length })
  for (let i = 0; i < dimension; i++) deviation[i] = Math.sqrt(deviation[i]) || 1
  return { mean, deviation }
}

/**
 * Fit by gradient descent on the negative ordinal log-likelihood.
 * `classWeights` defaults to none -- see the module note on why balancing hurt.
 */
export function trainOrdinal(rows, { epochs = 2500, rate = 0.15, l2 = 0.05, classWeights = null } = {}) {
  const dimension = rows[0].x.length
  const { mean, deviation } = standardize(rows)
  const prepared = rows.map(row => ({
    y: row.y,
    x: row.x.map((value, i) => (value - mean[i]) / deviation[i]),
    weight: classWeights ? (classWeights[row.y] ?? 1) : 1,
  }))

  const weights = Array(dimension).fill(0)
  let rawThresholds = [-1, Math.log(1), Math.log(1)]

  for (let epoch = 0; epoch < epochs; epoch++) {
    const theta = thresholds(rawThresholds)
    const weightGradient = Array(dimension).fill(0)
    const thetaGradient = [0, 0, 0]
    let totalWeight = 0

    for (const row of prepared) {
      const score = row.x.reduce((sum, value, i) => sum + value * weights[i], 0)
      totalWeight += row.weight
      // P(y >= k) for k = 1..3, with the implicit P(y >= 0) = 1 and P(y >= 4) = 0.
      const cumulative = theta.map(t => sigmoid(score - t))
      const probability = [
        1 - cumulative[0],
        cumulative[0] - cumulative[1],
        cumulative[1] - cumulative[2],
        cumulative[2],
      ]
      const observed = Math.max(EPSILON, probability[row.y])
      // d(-log P(y)) / d(score) and / d(theta_k), via the cumulative terms.
      const upper = row.y > 0 ? cumulative[row.y - 1] : null
      const lower = row.y < 3 ? cumulative[row.y] : null
      const upperDerivative = upper === null ? 0 : upper * (1 - upper)
      const lowerDerivative = lower === null ? 0 : lower * (1 - lower)
      const scoreGradient = -row.weight * (upperDerivative - lowerDerivative) / observed
      for (let i = 0; i < dimension; i++) weightGradient[i] += scoreGradient * row.x[i]
      if (row.y > 0) thetaGradient[row.y - 1] += row.weight * upperDerivative / observed
      if (row.y < 3) thetaGradient[row.y] -= row.weight * lowerDerivative / observed
    }

    const step = rate / Math.sqrt(1 + epoch / 200)
    for (let i = 0; i < dimension; i++) {
      weights[i] -= step * (weightGradient[i] / totalWeight + l2 * weights[i])
    }
    // Chain the threshold gradients through the exp() re-parameterisation.
    const scaled = [
      thetaGradient[0] + thetaGradient[1] + thetaGradient[2],
      (thetaGradient[1] + thetaGradient[2]) * Math.exp(rawThresholds[1]),
      thetaGradient[2] * Math.exp(rawThresholds[2]),
    ]
    for (let i = 0; i < 3; i++) rawThresholds[i] -= step * (scaled[i] / totalWeight)
  }

  const theta = thresholds(rawThresholds)
  const scoreOf = x => x.reduce((sum, value, i) => sum + ((value - mean[i]) / deviation[i]) * weights[i], 0)
  return {
    weights, theta, mean, deviation,
    /** Latent score; also the natural ranking key. */
    score: scoreOf,
    probabilities(x) {
      const cumulative = theta.map(t => sigmoid(scoreOf(x) - t))
      return [1 - cumulative[0], cumulative[0] - cumulative[1], cumulative[1] - cumulative[2], cumulative[2]]
    },
    predict(x) {
      const score = scoreOf(x)
      return theta.reduce((tier, t) => (score >= t ? tier + 1 : tier), 0)
    },
  }
}

/** Multiclass metrics plus the ordinal-aware ones: QWK and adjacent accuracy. */
export function ordinalMetrics(gold, predicted) {
  const labels = [0, 1, 2, 3]
  const matrix = labels.map(a => labels.map(b => gold.filter((y, i) => y === a && predicted[i] === b).length))
  const n = gold.length || 1
  const accuracy = gold.filter((y, i) => y === predicted[i]).length / n
  const adjacent = gold.filter((y, i) => Math.abs(y - predicted[i]) <= 1).length / n
  const mae = gold.reduce((sum, y, i) => sum + Math.abs(y - predicted[i]), 0) / n

  const f1 = labels.map(c => {
    const tp = matrix[c][c]
    const fp = labels.reduce((sum, o) => sum + (o === c ? 0 : matrix[o][c]), 0)
    const fn = labels.reduce((sum, o) => sum + (o === c ? 0 : matrix[c][o]), 0)
    const precision = tp / Math.max(1, tp + fp), recall = tp / Math.max(1, tp + fn)
    return 2 * precision * recall / Math.max(EPSILON, precision + recall)
  })

  // Quadratic weighted kappa: the right headline for an ordinal target, since it
  // charges a 0-vs-3 error nine times what it charges a 0-vs-1 error.
  const goldCount = labels.map(c => gold.filter(y => y === c).length)
  const predictedCount = labels.map(c => predicted.filter(y => y === c).length)
  let observed = 0, expected = 0
  for (const a of labels) for (const b of labels) {
    const penalty = (a - b) ** 2 / 9
    observed += penalty * matrix[a][b]
    expected += penalty * goldCount[a] * predictedCount[b] / n
  }
  const qwk = expected > 0 ? 1 - observed / expected : 0

  return {
    accuracy, adjacent_accuracy: adjacent, macro_f1: f1.reduce((a, b) => a + b) / 4, qwk, mae,
    confusion_matrix: matrix,
    prediction_distribution: Object.fromEntries(labels.map(c => [c, predictedCount[c]])),
  }
}
