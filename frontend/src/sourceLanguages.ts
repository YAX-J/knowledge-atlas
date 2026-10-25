/** Shared frontend file selection and display; backend validates the actual type. */
const extensions: Record<string, string> = {
  md: 'markdown', markdown: 'markdown', java: 'java', py: 'python', pyi: 'python',
  js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'jsx',
  ts: 'typescript', mts: 'typescript', cts: 'typescript', tsx: 'tsx', go: 'go',
  c: 'c', h: 'c', cpp: 'cpp', cc: 'cpp', cxx: 'cpp', hpp: 'cpp', hh: 'cpp', hxx: 'cpp', cs: 'csharp',
}
export const sourceFileAccept = Object.keys(extensions).map(ext => `.${ext}`).join(',')
export const sourceTypes = [...new Set(Object.values(extensions))]
export const sourceLanguageHint = 'Markdown、Java、Python、JavaScript/JSX、TypeScript/TSX、Go、C、C++、C#'
export function sourceTypeForFile(name: string): string | undefined {
  return extensions[name.split('.').pop()?.toLowerCase() ?? '']
}
export function isCodeSource(type: string): boolean {
  return type !== 'markdown' && Object.values(extensions).includes(type)
}
export function sourceTypeLabel(type: string): string {
  return ({ markdown: 'MD', python: 'PY', javascript: 'JS', typescript: 'TS', csharp: 'C#', cpp: 'C++' } as Record<string, string>)[type] ?? type.toUpperCase()
}
