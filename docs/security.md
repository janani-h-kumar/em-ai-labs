Accepted Risk:
- PYSEC-2026-76
- PYSEC-2026-77
- GHSA-gr75-jv2w-4656

Reason:
Upgrading to LangChain 1.x introduces substantial breaking changes.
Current deployment does not expose vulnerable attack paths:
- no untrusted image URL processing
- no HTML splitter URL ingestion
- validated outbound HTTP access
- no LangChain file-search middleware or document loaders in use
  (GHSA-gr75-jv2w-4656 requires resolving filesystem paths or search
  patterns from untrusted input; LangChainRuntime only performs chat/
  agent execution, no file loaders are wired into the harness)