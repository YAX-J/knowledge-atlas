// Trusted helper: type-check virtual same-package sources without executing a user's program.
package main

import (
    "encoding/json"
    "go/ast"
    "go/importer"
    "go/parser"
    "go/token"
    "go/types"
    "os"
    "path"
    "runtime"
)

type Source struct { Path string `json:"path"`; Content string `json:"content"` }
type Input struct { Path string `json:"path"`; Sources []Source `json:"sources"` }
type Target struct { Path string `json:"path"`; Line int `json:"line"`; EndLine int `json:"end_line"`; Name string `json:"name"`; Identity string `json:"identity"` }
type Call struct { Line int `json:"line"`; Column int `json:"column"`; Expression string `json:"expression"`; Target *Target `json:"target"` }

func main() {
    var input Input
    if json.NewDecoder(os.Stdin).Decode(&input) != nil { os.Exit(2) }
    fileset := token.NewFileSet()
    files := []*ast.File{}
    sources := map[string]string{}
    var selected *ast.File
    diagnostics := []map[string]interface{}{}
    for _, source := range input.Sources {
        if path.Dir(source.Path) != path.Dir(input.Path) { continue }
        file, err := parser.ParseFile(fileset, source.Path, source.Content, parser.AllErrors)
        if err != nil { diagnostics = append(diagnostics, map[string]interface{}{"kind":"syntax", "path":source.Path}) }
        if file == nil { continue }
        if source.Path == input.Path { selected = file }
        files = append(files, file)
        sources[source.Path] = source.Content
    }
    if selected == nil { os.Exit(3) }
    info := &types.Info{Uses:map[*ast.Ident]types.Object{}, Defs:map[*ast.Ident]types.Object{}, Selections:map[*ast.SelectorExpr]*types.Selection{}}
    configuration := types.Config{Importer:importer.Default(), Error:func(err error) {
        if len(diagnostics)<100 { diagnostics = append(diagnostics,map[string]interface{}{"kind":"type-context"}) }
    }}
    _, _ = configuration.Check("ka/"+path.Dir(input.Path), fileset, files, info)
    declarations := map[types.Object]*Target{}
    for _, file := range files {
        ast.Inspect(file,func(node ast.Node) bool {
            if declaration,ok:=node.(*ast.FuncDecl); ok {
                object:=info.Defs[declaration.Name]
                start,end:=fileset.Position(declaration.Pos()),fileset.Position(declaration.End())
                if object!=nil { declarations[object]=&Target{start.Filename,start.Line,end.Line,declaration.Name.Name,object.String()} }
            }
            return true
        })
    }
    calls:=[]Call{}
    ast.Inspect(selected,func(node ast.Node) bool {
        if len(calls)>=100 { return false }
        expression,ok:=node.(*ast.CallExpr)
        if !ok { return true }
        var object types.Object
        function:=expression.Fun
        if indexed,ok:=function.(*ast.IndexExpr); ok { function=indexed.X }
        if indexed,ok:=function.(*ast.IndexListExpr); ok { function=indexed.X }
        switch item:=function.(type) {
        case *ast.Ident: object=info.Uses[item]
        case *ast.SelectorExpr:
            if selection:=info.Selections[item]; selection!=nil { object=selection.Obj() } else { object=info.Uses[item.Sel] }
        }
        position:=fileset.Position(expression.Pos())
        begin, end:=fileset.Position(expression.Fun.Pos()).Offset,fileset.Position(expression.Fun.End()).Offset
        content:=sources[input.Path]
        text:=""
        if begin>=0 && end<=len(content) { text=content[begin:end] }
        calls=append(calls,Call{position.Line,position.Column,text,declarations[object]})
        return len(calls)<100
    })
    json.NewEncoder(os.Stdout).Encode(map[string]interface{}{"engine":runtime.Version()+"-types-same-package", "calls":calls, "diagnostics":diagnostics, "truncated":len(calls)>=100})
}
