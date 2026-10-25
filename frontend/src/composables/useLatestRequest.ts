import { onScopeDispose, ref, shallowRef } from 'vue'

/** Only the latest request in the current context may update visible state. */
export function useLatestRequest<T>(describeError: (error: unknown) => string) {
  const result = shallowRef<T | null>(null)
  const loading = ref(false)
  const error = ref('')
  let sequence = 0

  function clear() {
    sequence++
    result.value = null
    error.value = ''
    loading.value = false
  }

  async function run(operation: () => Promise<T>, sameContext: () => boolean) {
    const request = ++sequence
    result.value = null
    error.value = ''
    loading.value = true
    try {
      const value = await operation()
      if (request === sequence && sameContext()) result.value = value
    } catch (cause) {
      if (request === sequence && sameContext()) error.value = describeError(cause)
    } finally {
      if (request === sequence) loading.value = false
    }
  }

  onScopeDispose(clear)
  return { result, loading, error, clear, run }
}
