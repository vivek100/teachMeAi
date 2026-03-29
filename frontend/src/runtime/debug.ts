const DEBUG_ENABLED =
  (import.meta.env.VITE_DEBUG_LOGS ?? 'true').toLowerCase() !== 'false'

type LogValue = Record<string, unknown> | undefined

function format(scope: string, message: string) {
  return `TeachWithMeAI ${scope}: ${message}`
}

export const runtimeDebug = {
  info(scope: string, message: string, data?: LogValue) {
    if (!DEBUG_ENABLED) return
    console.info(format(scope, message), data ?? {})
  },
  warn(scope: string, message: string, data?: LogValue) {
    if (!DEBUG_ENABLED) return
    console.warn(format(scope, message), data ?? {})
  },
  error(scope: string, message: string, data?: LogValue) {
    if (!DEBUG_ENABLED) return
    console.error(format(scope, message), data ?? {})
  },
  debug(scope: string, message: string, data?: LogValue) {
    if (!DEBUG_ENABLED) return
    console.debug(format(scope, message), data ?? {})
  },
}
