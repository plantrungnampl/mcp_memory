# Appendix C — Export Format

## 1) Scope
- Export hiện là **control-plane workflow**
- Format canonical hiện tại: **JSON v1**
- Import vẫn out-of-scope

## 2) Delivery flow
1. owner tạo export qua control-plane route
2. worker build artifact
3. backend trả export record + signed download URL khi ready

## 3) Artifact schema
Top-level:

```json
{
  "format": "viberecall-export",
  "version": "1.0",
  "exported_at": "2026-03-08T12:00:00Z",
  "project_id": "proj_...",
  "episodes": [],
  "entities": [],
  "facts": [],
  "relationships": []
}
```

### Episode row
- `episode_id`
- `reference_time`
- `ingested_at`
- `summary`
- `metadata`

### Entity row
- `entity_id`
- `type`
- `name`

### Fact row
- `fact_id`
- `text`
- `valid_at`
- `invalid_at`
- `ingested_at`
- `provenance.episode_ids`
- `provenance.reference_time`
- `provenance.ingested_at`

### Relationship row
- `type`
- `source_id`
- `target_id`

## 4) Notes
- IDs được preserve
- Export artifact hiện tập trung vào episodes/facts/entities/relationships, không bao gồm full code-index snapshot
