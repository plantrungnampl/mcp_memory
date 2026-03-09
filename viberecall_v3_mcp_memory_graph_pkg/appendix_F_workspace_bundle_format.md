---
title: Workspace Bundle Format
status: normative
version: 3.0
---
# Appendix F — Workspace Bundle Format

## 1. Purpose
Bundle format cho phép local workspace được index bởi remote service mà không cần raw path access.

## 2. Container
Recommended:
- `.tar.gz` or `.zip`
- top-level `manifest.json`
- regular files only
- symlinks either rejected or represented as metadata entries, never blindly followed out of root

## 3. `manifest.json`
Suggested shape:
```json
{
  "format_version": 1,
  "repo_name": "payments-service",
  "root_relative": ".",
  "generated_at": "2026-03-08T12:00:00Z",
  "git": {
    "head_commit": "abc123",
    "branch": "feature/refactor",
    "base_commit": "def456",
    "is_dirty": true
  },
  "files": [
    {
      "path": "src/auth/session.py",
      "sha256": "...",
      "size_bytes": 1234,
      "mode": "0644"
    }
  ]
}
```

## 4. Validation rules
Server/worker MUST reject:
- absolute paths
- `..` traversal
- device files
- huge files over policy
- invalid manifests
- mismatched file hashes if verified

## 5. Optional diff metadata
Bundle MAY include:
- changed files list
- deleted paths
- patch against base commit

Nhưng v1 có thể vẫn build full snapshot from bundle contents.

## 6. Security note
Bundle content là untrusted input.
Never execute code from bundle as part of indexing unless explicitly sandboxed and allowed by product design.
