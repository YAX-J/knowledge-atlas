# Multi-language code parsing V1

[简体中文](MULTILANGUAGE_PARSING.zh-CN.md)

## Implemented scope

Single-file and bounded folder uploads (50 supported files), explicit GitHub file synchronization, manual parsing and the Worker share the source registry. UTF-8, size, empty-input, path and user/project/repository checks remain enforced. Deduplication includes source type and byte hash, never crossing languages. No migration is required; head remains `20261023_0015`.

| Source type | Extensions | Structure |
| --- | --- | --- |
| `markdown` | `.md .markdown` | Existing heading/paragraph/list/code chunks |
| `java` | `.java` | Existing Java V1, stable identities and bounded repository call analysis |
| `python` | `.py .pyi` | Classes, functions/methods and simple class attributes; decorator text retained |
| `javascript` | `.js .mjs .cjs` | Classes, methods, fields, declared functions and named variable-bound functions |
| `jsx` | `.jsx` | JavaScript structure with JSX syntax |
| `typescript` | `.ts .mts .cts` | Classes/interfaces/type aliases, fields/properties, functions/methods |
| `tsx` | `.tsx` | TypeScript structure with TSX syntax |
| `go` | `.go` | Types, struct fields, functions and receiver methods |
| `c` | `.c .h` | Named structs/unions/enums, fields, function definitions/prototypes |
| `cpp` | `.cpp .cc .cxx .hpp .hh .hxx` | Named types, fields, functions/methods and some namespace qualification |
| `csharp` | `.cs` | Named classes/structs/interfaces/records, fields/properties, methods/constructors |

Extensions are case-insensitive. `.h` deterministically means C; use `.hpp/.hh/.hxx` for C++ headers. There is no content guessing or complete-language guarantee.

## Evidence, outlines and search

- New languages use pinned Tree-sitter and official language wheels installed with dependencies. Parsing never downloads grammars, executes source, loads project dependencies or calls models. The separate explicit Agent action may call the configured model after parsing.
- Every original line, including whitespace/error text, belongs to exactly one ordered whole-line chunk, at most 120 lines each. Type/function boundaries take priority; long functions may span chunks. Hashes and UUIDs are deterministic.
- Outlines and symbol search share UUIDs and line ranges. Existing `type/field/method` kinds mean types, fields/properties and functions/methods. Hits add `language`; structure adds `language` and `has_syntax_errors`.
- Each file is bounded to 200 symbols and 100,000 syntax-node visits, with `truncated` when exceeded. Search retains its 100-source/20 MiB budget and default 50/maximum 100 hits.
- Parser recovery sets `has_syntax_errors=true` in structure/search, omitting declarations containing errors while possibly retaining valid local declarations. Successful parsing means referenceable source, not successful compilation. Syntax errors are separate from truncation.
- The desktop UI displays language badges, syntax warnings, outlines and exact source chunks. Search navigation focuses the original chunk UUID/page; GitHub hits retain commit-pinned line links.

## Existing GitHub snapshots

Default complete-same-commit caching is preserved. Old complete snapshots may omit newly supported extensions. Select the repository card's rescan checkbox or send `{"rescan":true}` to reread the same commit tree, reuse compatible known blobs/tasks and discover new languages. File/byte limits still apply; historical sources are not deleted and formal knowledge is not automatically created.

## Limits and verification

Default parsing for new languages does not resolve cross-file calls/import targets, infer types, expand macros, instantiate generics or model runtime behavior. An explicit Agent action can compare locally extracted calls with exact-name declarations in ready sources from the same repository and compatible language family. The backend limits and validates every candidate ID and returns exact call/declaration lines; it still does not provide compiler semantics, external dependencies, dynamic dispatch or persistent relationships. Java keeps its deterministic bounded analysis. All structure and Agent output remain derived source data, not authoritative knowledge, and cannot bypass review. See [ADR 0041](adr/0041-bounded-multilanguage-agent-call-analysis.md).

Focused tests: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_multilanguage.py tests/test_code_agent.py`. SQLite, simulated GitHub, and mocked Agent output do not establish native PostgreSQL or real-provider/model quality. Install/update dependencies in `backend` with `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`.

### Verification on 2026-10-23

The user selected agent execution. All 46 new focused tests passed. Final backend suite: 534 passed, 4 explicit native/network tests skipped, 1 existing Starlette deprecation warning, 31.28 seconds. Frontend `npm run build` passed. Desktop Chrome at 1440×1100 with disposable SQLite fixtures passed Python upload/parsing, Python+TSX folder/repository import, TSX outlines/search, source-preserving syntax warnings, unsupported-file feedback and keyboard search/exact-chunk focus. Active element and target chunk IDs matched; no horizontal overflow. Search-region axe: 22 passes, 0 violations, 0 incomplete. Simulated GitHub covers nine new syntaxes, pinned line links, cache reuse and old complete-snapshot rescans. No migration, business database writes, real GitHub or model calls. Screenshots/fixtures remain ignored under `output/`.
