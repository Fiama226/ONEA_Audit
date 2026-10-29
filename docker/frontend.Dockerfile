# ONEA frontend image: Vite build served by nginx. Build context: repository root.
#   docker build -f docker/frontend.Dockerfile -t onea-frontend \
#     --build-arg VITE_API_URL=https://audit.onea.bf \
#     --build-arg VITE_OIDC_AUTHORITY=https://sso.onea.bf/realms/onea .
FROM node:22.23.4-alpine3.24@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./

# VITE_* values are inlined into the bundle at build time.
ARG VITE_API_URL
ARG VITE_OIDC_AUTHORITY
ARG VITE_OIDC_CLIENT_ID=onea-frontend
ENV VITE_API_URL=$VITE_API_URL \
    VITE_OIDC_AUTHORITY=$VITE_OIDC_AUTHORITY \
    VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID
# Fail fast: an empty authority would bake a SPA that can never log in.
RUN test -n "$VITE_OIDC_AUTHORITY" || { echo "VITE_OIDC_AUTHORITY build-arg is required" >&2; exit 1; }
RUN npm run build

FROM nginx:1.27.5-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 AS runtime
COPY docker/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO /dev/null http://127.0.0.1/ || exit 1
