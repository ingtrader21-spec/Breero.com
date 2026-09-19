# syntax=docker/dockerfile:1.7
ARG APP_NAME
FROM node:22-alpine AS base
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@10.0.0 --activate
WORKDIR /app

FROM base AS dependencies
ARG APP_NAME
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json ./
COPY apps/${APP_NAME}/package.json apps/${APP_NAME}/package.json
COPY packages/portal/package.json packages/portal/package.json
RUN pnpm install --frozen-lockfile

FROM dependencies AS build
ARG APP_NAME
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NODE_ENV=production
COPY apps/${APP_NAME} apps/${APP_NAME}
COPY packages/portal packages/portal
RUN pnpm --filter @breero/${APP_NAME} build

FROM node:22-alpine AS runtime
ARG APP_NAME
ENV NODE_ENV=production
ENV PORT=3000
ENV APP_NAME=$APP_NAME
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
 && addgroup -S -g 10001 breero && adduser -S -u 10001 -G breero breero
WORKDIR /app
COPY --from=build --chown=breero:breero /app/apps/${APP_NAME}/.next/standalone ./
COPY --from=build --chown=breero:breero /app/apps/${APP_NAME}/.next/static ./apps/${APP_NAME}/.next/static
USER breero
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD wget -qO- http://127.0.0.1:3000/health >/dev/null || exit 1
CMD ["sh", "-c", "exec node apps/$APP_NAME/server.js"]
