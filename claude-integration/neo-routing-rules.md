# RLM Sandbox Routing Rules

When the `rlm` MCP server is available, follow these rules to decide when to use it vs. built-in tools.

## File Loading

- Files **over 200 lines**: use `rlm_load` to bring the file into the sandbox as a variable, then process it there. This keeps large content out of the context window.
- Files under 200 lines: use `Read` as usual.

## Code Execution

- **Multi-file analysis** (comparing files, aggregating data across sources): use `rlm_exec` to run Python in the sandbox. Store intermediate results as sandbox variables rather than printing everything back.
- **Large data processing** (CSV parsing, JSON transformation, text manipulation over big inputs): always use the sandbox. Do not attempt inline code blocks for anything over a few hundred lines of data.
- **Quick one-liners** (simple calculations, string formatting): either inline or sandbox is fine.

## Sub-Agent Tasks

- Use `rlm_sub_agent` when the task benefits from DSPy optimization — multi-step reasoning, structured extraction, or tasks that improve with few-shot examples.
- Provide a clear `signature` string (e.g., `"question -> answer"`) and matching `inputs` dict.

## Variable Management

- After running computations, store meaningful results in named sandbox variables.
- Retrieve results with `rlm_get` — use the `query` parameter to run expressions against stored data without pulling everything back.
- Use `rlm_vars` to check what's currently in the sandbox before running new code.

## Apple / Swift / iOS Documentation

When building iOS apps or working with Apple frameworks:

1. **Search first**: `rlm_apple_search("NavigationStack")` — fast heading search across pre-exported Apple docs (SwiftUI, Foundation, Vision, RealityKit, etc.)
2. **Read specific sections**: `rlm_apple_read("docs/apple/swiftui.md", anchor="documentation-swiftui-navigationstack")` — targeted section extraction without loading the full 3.3MB file
3. **Export missing frameworks**: `rlm_apple_export("combine")` — exports from local Dash docset, indexes into knowledge store. Only needed once per framework.
4. **Context7 for third-party Swift libs**: Use Context7 MCP tools (`resolve-library-id` + `query-docs`) for non-Apple libraries (TCA, Alamofire, etc.), then pipe the result into `rlm_context7_ingest(library, content)` to persist it in the knowledge store.
5. **After indexing**, use `rlm_search` / `rlm_ask` to query everything (Apple docs + Context7 docs + any other indexed content) from one place.

**Workflow for a new iOS feature:**
```
rlm_apple_search("Observable")           # find relevant API docs
rlm_apple_read(path, anchor)             # read the specific section
rlm_search("Observable SwiftUI pattern") # check knowledge store for prior research
# ... implement the feature using accurate docs ...
```

## Recursive Execution (llm_query)

`llm_query(prompt)` is available in all `rlm_exec` calls. It calls Haiku 4.5 on the host — API keys never enter the sandbox. Use this for:

- **Batch processing large data**: load data into sandbox, loop through it calling `llm_query()` for each chunk. Only final results enter your context.
- **Multi-step reasoning**: write code that chains LLM calls — summarize, then extract, then classify — all in sandbox code.
- **Recursive comprehension**: process a large corpus by having sub-LMs summarize sections, then synthesize across summaries.

**Example — processing Bible chapters without filling context:**
```python
# via rlm_exec:
summaries = []
for ch in chapters[:10]:
    s = llm_query(f"Summarize key theological themes: {ch[:3000]}")
    summaries.append(s)
themes = llm_query(f"Synthesize themes across chapters: {summaries}")
```

Claude never sees the raw chapter text. Only `themes` comes back via `rlm_get`.

**When to use llm_query vs rlm_sub_agent:**
- `llm_query()` in `rlm_exec` — you control the loop, the logic, the data flow. True recursive pattern.
- `rlm_sub_agent` — DSPy controls the loop. Better when you want DSPy's optimization (few-shot, prompt tuning).

## When NOT to Use the Sandbox

- Reading small config files or source code for understanding — use `Read`.
- Simple file edits — use `Edit`.
- Git operations — use `Bash`.
- The sandbox is for computation, not for replacing standard file operations.
