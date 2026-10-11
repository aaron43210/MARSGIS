# syntax=docker/dockerfile:1.7
# MarsGIS frontend image -> ghcr.io/${GHCR_OWNER}/marsgis-frontend
#
# Stage 1: Vite build on node:24 (LTS pin; host node 26 is local-dev only).
# Stage 2: static serve on nginx-unprivileged (listens 8080, runs non-root).
#
# All VITE_* configuration is compile-time. In the published image the SPA is
# served same-origin behind nginx, which reverse-proxies /api to the backend, so
# VITE_API_URL defaults to "/".
ARG NODE_VERSION=24

# ----------------------------------------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS build
ENV CI=true
WORKDIR /app
COPY package.json package-lock.json* ./
# `npm ci` requires a committed lockfile; fall back to `npm install` when the
# frontend concern has not committed package-lock.json yet.
RUN if [ -f package-lock.json ]; then npm ci --include=dev; else npm install --include=dev; fi
COPY . .
ARG VITE_API_URL="/"
ARG VITE_USE_MOCKS="false"
ARG VITE_DEFAULT_BASEMAP="viking"
ARG VITE_CESIUM_BASE_URL="/cesium"
ARG VITE_TREK_VIA_PROXY="false"
ENV VITE_API_URL=${VITE_API_URL} \
    VITE_USE_MOCKS=${VITE_USE_MOCKS} \
    VITE_DEFAULT_BASEMAP=${VITE_DEFAULT_BASEMAP} \
    VITE_CESIUM_BASE_URL=${VITE_CESIUM_BASE_URL} \
    VITE_TREK_VIA_PROXY=${VITE_TREK_VIA_PROXY}
RUN npm run build

# ----------------------------------------------------------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS serve
LABEL org.opencontainers.image.title="marsgis-frontend" \
      org.opencontainers.image.description="MarsGIS React + CesiumJS single-page app served by nginx" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/aaron43210/MARSGIS"
# nginx-unprivileged runs as a non-root user and listens on 8080 by default.
# BACKEND_UPSTREAM is substituted into the config at container start via the
# stock nginx `envsubst`-on-templates mechanism.
ENV BACKEND_UPSTREAM="http://backend:8000"
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD ["wget", "-qO", "/dev/null", "http://127.0.0.1:8080/healthz"]
