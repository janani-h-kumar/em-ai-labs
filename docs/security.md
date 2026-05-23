Accepted Risk:
- PYSEC-2026-76
- PYSEC-2026-77

Reason:
Upgrading to LangChain 1.x introduces substantial breaking changes.
Current deployment does not expose vulnerable attack paths:
- no untrusted image URL processing
- no HTML splitter URL ingestion
- validated outbound HTTP access