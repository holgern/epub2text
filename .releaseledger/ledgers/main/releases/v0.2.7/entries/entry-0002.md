---
schema_version: 2
object_type: release_entry
versioning:
  schema_version: 1
  revision: 1
entry_id: entry-0002
release_version: v0.2.7
kind: added
summary:
  Annotated structured extraction blocks with navigation context from EPUB TOC,
  assigning chapter IDs and titles to text blocks
status: accepted
audience: null
scopes: []
source_refs:
  - git:09ece97319945bad28b1769e211909e8ab7b1518
paths:
  - epub2text/toc_map.py
  - epub2text/parser.py
  - tests/test_structured_extraction.py
issues: []
prs: []
sources:
  - git:09ece97319945bad28b1769e211909e8ab7b1518
breaking: false
internal: false
order: 2
---

During structured extraction, text blocks now receive chapter_id and chapter_title from
the nearest active navigation entry. The toc_map module handles whole-document hrefs,
nested TOC entries (deepest active entry wins), multi-document EPUBs, and unresolved
fragments. Navigation entries from the "fallback" source are excluded.
