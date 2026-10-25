import { effectScope } from 'vue'
import { expect, it } from 'vitest'
import { useLatestRequest } from '../src/composables/useLatestRequest'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

it('does not let an older failure stop or overwrite a newer search', async () => {
  const scope = effectScope()
  const state = scope.run(() => useLatestRequest<string>(String))!
  const old = deferred<string>(), current = deferred<string>()
  const first = state.run(() => old.promise, () => true)
  const second = state.run(() => current.promise, () => true)
  old.reject(new Error('Old failure'))
  await first
  expect(state.loading.value).toBe(true)
  expect(state.error.value).toBe('')
  current.resolve('New evidence')
  await second
  expect(state.result.value).toBe('New evidence')
  expect(state.loading.value).toBe(false)
  scope.stop()
})

it('drops replies after clear, project change and component disposal', async () => {
  const scope = effectScope()
  const state = scope.run(() => useLatestRequest<string>(String))!
  let project = 'first'
  const old = deferred<string>()
  const first = state.run(() => old.promise, () => project === 'first')
  project = 'second'
  old.resolve('Wrong project')
  await first
  expect(state.result.value).toBeNull()
  const cleared = deferred<string>()
  const second = state.run(() => cleared.promise, () => true)
  state.clear()
  cleared.resolve('Cleared answer')
  await second
  expect(state.result.value).toBeNull()
  const disposed = deferred<string>()
  const third = state.run(() => disposed.promise, () => true)
  scope.stop()
  disposed.reject(new Error('Disposed failure'))
  await third
  expect(state.error.value).toBe('')
  expect(state.loading.value).toBe(false)
})
