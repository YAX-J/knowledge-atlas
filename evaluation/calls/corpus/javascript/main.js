import * as a from './a.js'
import * as b from './b.js'
export function run(unknown, flag) {
  a.unique()
  a.save()
  unknown.save()
  external_missing()
  const selected = flag ? a : b
  selected.save()
}
