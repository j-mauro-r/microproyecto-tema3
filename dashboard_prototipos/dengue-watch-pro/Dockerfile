# Lives inside this directory (not under docker/) on purpose: its COPY
# instructions assume the build context IS this directory, and some
# platforms (confirmed: Railway) resolve a Dockerfile referenced from
# outside its intended context incorrectly, breaking `COPY package.json`.
# Build context = this directory:
#   docker build -f dashboard_prototipos/dengue-watch-pro/Dockerfile \
#     --build-arg VITE_BIOMAC_API_BASE_URL=http://<api-url>/api/v2 \
#     -t biomac-dashboard dashboard_prototipos/dengue-watch-pro

# bun.lock (not the stale package-lock.json) is this project's source of
# truth -- bunfig.toml carries bun-specific supply-chain settings
# (minimumReleaseAge guard) that only apply under bun.
FROM oven/bun:1-slim AS builder
WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

# The Lovable/TanStack vite config defaults Nitro's preset to
# "cloudflare-module". Outside the Lovable sandbox, NITRO_PRESET overrides
# that default, producing a plain Node server at .output/server/index.mjs
# instead of a Cloudflare Worker module.
ARG VITE_BIOMAC_API_BASE_URL
ENV VITE_BIOMAC_API_BASE_URL=$VITE_BIOMAC_API_BASE_URL \
    NITRO_PRESET=node-server
RUN bun run build

FROM node:22-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /app/.output ./.output

ENV NODE_ENV=production \
    PORT=3000

USER appuser
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
