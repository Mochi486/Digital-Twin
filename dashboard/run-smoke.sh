#!/usr/bin/env sh
set -eu
IMAGE=project70-dashboard-smoke
CONTAINER=project70-dashboard-smoke
docker build -f dashboard/Dockerfile -t "$IMAGE" .
docker run -d --rm --name "$CONTAINER" -p 8501:8501 "$IMAGE"
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; docker image rm "$IMAGE" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8501/_stcore/health >/dev/null; then
    curl -fsS http://127.0.0.1:8501/ >/dev/null
    exit 0
  fi
  sleep 1
done
exit 1
