import * as a from './a'
import * as b from './b'
declare function external_missing(): void
export function run(unknown: { save(): number }, flag: boolean) {
  a.unique()
  a.save()
  unknown.save()
  external_missing()
  const selected = flag ? a : b
  selected.save()
}
