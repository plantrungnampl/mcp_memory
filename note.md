Làm đúng thứ tự này trên Droplet.

  1. Vào máy

  ssh root@167.172.66.155
  cd /srv/viberecall

  2. Xem container có đang sống không

  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production ps

  Bạn cần thấy ít nhất:

  - ops-api-1
  - ops-worker-1
  - ops-redis-1
  - ops-falkordb-1

  Nếu worker không Up, đó là nghi phạm số 1.

  3. Check health backend

  curl http://127.0.0.1:8010/healthz

  Nếu status không phải ok, xử lý backend trước.

  4. Xem log worker
docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production logs --since=5m worker

  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production logs --tail=200 worker

  Nếu muốn follow live:

  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production logs -f worker

  Tìm các dấu hiệu kiểu:

  - ERROR
  - Traceback
  - failed
  - graphiti
  - outbox
  - celery

  5. Xem log API

  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production logs --tail=200 api

  Nếu save path có vấn đề, hay thấy các dòng kiểu:

  - save_outbox_dispatch_failed_after_commit
  - request save thành công nhưng không dispatch tiếp được

  6. Check worker có đang nghe queue không

  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production exec worker celery -A viberecall_mcp.workers.celery_app inspect active_queues

  Bạn muốn thấy queue memory.

  7. Check worker có task pending không

  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production exec worker celery -A viberecall_mcp.workers.celery_app inspect active
  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production exec worker celery -A viberecall_mcp.workers.celery_app inspect reserved
  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production exec worker celery -A viberecall_mcp.workers.celery_app inspect scheduled

  8. Nếu worker chết hoặc treo, restart đúng stack

  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production up -d --build

  Hoặc restart riêng worker:

  docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production restart worker