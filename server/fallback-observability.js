export function fallbackEvent(stage, error, context = {}) {
  return {
    event: 'algorithm_fallback', stage,
    reason: error instanceof Error ? error.message : String(error || 'unknown_error'),
    context, timestamp: new Date().toISOString(),
  }
}

export function logAlgorithmFallback(stage, error, context = {}) {
  const event = fallbackEvent(stage, error, context)
  console.warn(JSON.stringify(event))
  return event
}
