package bench
func Run(a Alpha, unknown interface{Save() int}, flag bool) {
  Unique()
  a.Save()
  unknown.Save()
  externalMissing()
  var selected interface{Save() int} = a
  if !flag { selected = Beta{} }
  selected.Save()
}
