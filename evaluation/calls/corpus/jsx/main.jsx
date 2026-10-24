import * as a from './a.jsx'
import * as b from './b.jsx'
export function run(unknown, flag) {
  a.unique()
  a.save()
  unknown.save()
  external_missing()
  const selected = flag ? a : b
  selected.save()
}
