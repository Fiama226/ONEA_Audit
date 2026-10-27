# ONEA frontend image: Vite build served by nginx. Build context: repository root.
#   docker build -f docker/frontend.Dockerfile -t onea-frontend \
#     --build-arg VITE_API_URL=https://audit.onea.bf \
#     --build-arg VITE_OIDC_AUTHORITY=https://sso.onea.bf/realms/onea .
FROM node:22-alpine AS build

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

FROM nginx:1.27-alpine AS runtime
COPY docker/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO /dev/null http://127.0.0.1/ || exit 1
