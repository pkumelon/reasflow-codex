# Semantic Scholar API key

Use an API key when Introduction supplementation needs repeated S2 metadata lookups or unauthenticated requests are rate-limited. ReaScholar remains the primary source; the S2 key only enables enrichment and fallback.

## Apply

1. Open the official Semantic Scholar API page: <https://www.semanticscholar.org/product/api#api-key>.
2. Follow the API-key request link and submit the intended academic or research-tool use case.
3. Wait for Semantic Scholar to issue the key. Reasflow cannot create or retrieve a key on the user's behalf.

## Configure

Set the key in the environment that starts Codex:

```bash
export SEMANTIC_SCHOLAR_API_KEY="<issued-key>"
```

`S2_API_KEY` is accepted as a compatibility alias. Prefer `SEMANTIC_SCHOLAR_API_KEY`.

For a persistent local setup, store the export in a user-owned shell secret/configuration file that is not part of the research workspace, then restart Codex so subagents and subprocesses inherit it. In CI, use the platform's encrypted secret store.

Never write the key into `.env` files committed to the project, task JSON, retrieval traces, BibTeX, logs, prompts, or command arguments.

## Verify without exposing the key

```bash
test -n "${SEMANTIC_SCHOLAR_API_KEY:-${S2_API_KEY:-}}"
```

Then run a targeted retrieval through the skill. The trace records only `s2_api_key_configured: true|false`; it never records the value.

Semantic Scholar Graph API documentation: <https://api.semanticscholar.org/api-docs/graph>
