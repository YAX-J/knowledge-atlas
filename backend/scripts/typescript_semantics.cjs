/* Static compiler analysis over a virtual repository. No tsconfig, plugins, emit or user execution. */
const fs = require('node:fs');
const path = require('node:path');
const ts = require('../../frontend/node_modules/typescript/lib/typescript.js');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const files = new Map(input.sources.map(item => ['/ka/' + item.path, item]));
const options = { noEmit: true, noLib: true, allowJs: true, checkJs: true,
  target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler, jsx: ts.JsxEmit.Preserve };
const host = ts.createCompilerHost(options);
host.fileExists = name => files.has(name);
host.readFile = name => files.get(name)?.content;
host.directoryExists = dir => [...files.keys()].some(name => name.startsWith(dir + '/'));
host.getCurrentDirectory = () => '/ka';
host.getSourceFile = (name, version) => {
  const item = files.get(name);
  return item ? ts.createSourceFile(name, item.content, version, true) : undefined;
};
host.writeFile = () => { throw new Error('Emit is disabled'); };
const program = ts.createProgram([...files.keys()], options, host);
const checker = program.getTypeChecker();
const calls = [];
let visits = 0, truncated = false;
const file = program.getSourceFile('/ka/' + input.path);
function visit(node) {
  if (++visits > 100000 || calls.length >= 1000) { truncated = true; return; }
  if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
    const location = file.getLineAndCharacterOfPosition(node.getStart(file));
    const signature = checker.getResolvedSignature(node);
    const declaration = signature?.declaration;
    const targetFile = declaration?.getSourceFile();
    let target = null;
    if (targetFile && files.has(targetFile.fileName)) {
      const at = targetFile.getLineAndCharacterOfPosition(declaration.getStart(targetFile));
      target = { path: targetFile.fileName.slice(4), line: at.line + 1,
        end_line: targetFile.getLineAndCharacterOfPosition(declaration.end - 1).line + 1,
        identity: declaration.pos + ':' + declaration.end + ':' + checker.signatureToString(signature),
        name: declaration.name?.getText(targetFile) || '' };
    }
    calls.push({ line: location.line + 1, column: location.character + 1,
      expression: node.expression.getText(file), target });
  }
  ts.forEachChild(node, visit);
}
if (file) visit(file);
const diagnostics = [ ...program.getSyntacticDiagnostics(file).map(item => ({item, kind:'syntax'})),
  ...program.getSemanticDiagnostics(file).map(item => ({item, kind:'type-context'})) ].map(({item, kind}) => ({kind, code: item.code,
  line: item.start == null ? null : file.getLineAndCharacterOfPosition(item.start).line + 1}));
process.stdout.write(JSON.stringify({engine: 'typescript-' + ts.version, calls,
  diagnostics: diagnostics.slice(0,100), truncated: truncated || diagnostics.length > 100}));
