---
title: Code Indexing Design
status: normative
version: 3.0
---
# 08 — Code Indexing Design

## 1. Problem statement
Coding agents cần graph không chỉ từ notes mà còn từ codebase.
Nhưng hosted memory service **không được** đọc raw local repo path từ máy developer.

## 2. Supported repo sources
### A. `git`
Worker clone repo vào sandbox bằng:
- remote URL
- requested ref/commit
- optional credentials reference managed out-of-band

### B. `workspace_bundle`
Dành cho dirty local workspace hoặc repo private/local-only.
Bundle được tạo bởi local bridge hoặc owner helper rồi upload tới object storage.

Raw `repo_path` server-local là **forbidden**.

## 3. Optional local workspace bridge
Local bridge là companion process/tool:
- chạy local cạnh repo
- đọc workspace hiện tại
- build manifest + tar/zip bundle
- upload bundle qua pre-signed URL hoặc authenticated control-plane endpoint
- gọi `index_repo` với `bundle_ref`

Điều này phù hợp cho:
- uncommitted diffs
- local-only repos
- generated files trước khi push
- faster incremental developer workflows

## 4. Workspace bundle contents
Bundle SHOULD chứa:
- `manifest.json`
- file entries (path, sha256, size, mode, mime)
- optional git metadata (HEAD, branch, dirty files)
- optional base commit
- optional patch/diff metadata
- no device files / no arbitrary symlink traversal

Xem `appendix_F_workspace_bundle_format.md`.

## 5. Index run model
`code_index_runs` có lifecycle:
- `QUEUED`
- `RUNNING`
- `FAILED`
- `SUCCEEDED`

`code_index_snapshots` có lifecycle:
- `BUILDING`
- `VALIDATING`
- `READY`
- `INVALID`

`code_index_snapshot_heads` map project -> latest READY snapshot.

## 6. Atomicity invariant
Read path chỉ được nhìn thấy latest snapshot khi snapshot mới đã:
- parse xong
- validate xong
- persist đầy đủ metadata/chunks/edges
- passed integrity checks

Failed build không được làm mất snapshot cũ.

## 7. Extraction targets
Code indexing SHOULD extract:
- files/directories/modules
- classes/interfaces/functions/methods
- imports/calls/defines/implements/extends edges
- test coverage relationships where available
- config/service ownership hints where deterministic

## 8. Interaction with memory graph
Code index output có 2 lớp:
1. **code index canonical tables** cho snapshot-specific data
2. **memory graph facts/entities** cho stable, query-worthy relationships

Quy tắc:
- snapshot-specific raw parse data không nhất thiết phải thành memory facts hết
- only durable, meaningful relationships should be surfaced into general memory graph

## 9. Incremental indexing
V1 MAY start with full snapshot rebuild.
Later optimization:
- changed-file incremental parse
- stable symbol/entity resolution
- chunk reuse by hash

## 10. Sandbox security
Worker sandbox MUST:
- read bundle/clone into isolated workspace
- bound CPU, memory, time, disk
- disallow outbound network by default during parsing unless explicitly required
- reject path traversal / symlink escape
- treat bundle content as untrusted

## 11. Cost controls
- max files
- max total bytes
- max individual file size
- optional ignore patterns
- concurrent index cap per project
- bundle retention TTL

## 12. Recommended v1 behavior
- full snapshot only
- parsers for top target languages
- basic code structure and dependency edges
- latest READY head
- workspace bundle via local helper
- no raw repo path
