#!/usr/bin/env bash
# build-multiarch.sh — Constrói e publica imagens multi-arquitetura (amd64 + arm64)
#
# Pré-requisitos:
#   docker buildx create --use --name tempus-builder
#
# Uso:
#   ./docker/build-multiarch.sh [TAG] [REGISTRY]
#
# Exemplos:
#   ./docker/build-multiarch.sh                     # build local, tag: latest
#   ./docker/build-multiarch.sh v1.5.0              # build local, tag: v1.5.0
#   ./docker/build-multiarch.sh v1.5.0 docker.io/myuser  # build + push

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TAG="${1:-latest}"
REGISTRY="${2:-}"
PLATFORMS="linux/amd64,linux/arm64"

if [ -n "$REGISTRY" ]; then
  BACKEND_IMAGE="${REGISTRY}/tempus-backend:${TAG}"
  FRONTEND_IMAGE="${REGISTRY}/tempus-frontend:${TAG}"
  PUSH_FLAG="--push"
  echo ">>> Modo PUSH — imagens serão publicadas em ${REGISTRY}"
else
  BACKEND_IMAGE="tempus-backend:${TAG}"
  FRONTEND_IMAGE="tempus-frontend:${TAG}"
  # --load carrega apenas a imagem nativa no daemon local (buildx não suporta --load com múltiplos platforms)
  PUSH_FLAG="--load"
  PLATFORMS="linux/$(uname -m | sed 's/x86_64/amd64/' | sed 's/aarch64/arm64/')"
  echo ">>> Modo LOCAL — build apenas para plataforma nativa (${PLATFORMS})"
  echo "    Para build multi-arch real, forneça um REGISTRY como 2º argumento."
fi

# Garantir que o builder multi-arch existe
if ! docker buildx inspect tempus-builder &>/dev/null; then
  echo ">>> Criando builder multi-arch 'tempus-builder'..."
  docker buildx create --name tempus-builder --driver docker-container --use
fi
docker buildx use tempus-builder

echo ""
echo "=== Backend ==="
docker buildx build \
  --platform "${PLATFORMS}" \
  --file "${SCRIPT_DIR}/Dockerfile.backend" \
  --tag "${BACKEND_IMAGE}" \
  ${PUSH_FLAG} \
  "${PROJECT_ROOT}/backend"

echo ""
echo "=== Frontend ==="
docker buildx build \
  --platform "${PLATFORMS}" \
  --file "${SCRIPT_DIR}/Dockerfile.frontend" \
  --tag "${FRONTEND_IMAGE}" \
  ${PUSH_FLAG} \
  "${PROJECT_ROOT}"

echo ""
echo "✓ Build concluído."
echo "  Backend:  ${BACKEND_IMAGE}"
echo "  Frontend: ${FRONTEND_IMAGE}"
