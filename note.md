 cd /Data/VibeRecall_Memory/apps/mcp-api
  MEMORY_BACKEND=neo4j NEO4J_URI=bolt://localhost:7691 NEO4J_USER=neo4j NEO4J_PASSWORD=password uv run uvicorn viberecall_mcp.app:create_app --factory
  --host 0.0.0.0 --port 8010