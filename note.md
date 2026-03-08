 cd /Data/VibeRecall_Memory/apps/mcp-api
  MEMORY_BACKEND=falkordb FALKORDB_HOST=localhost FALKORDB_PORT=6380 uv run uvicorn viberecall_mcp.app:create_app --factory
  --host 0.0.0.0 --port 8010
