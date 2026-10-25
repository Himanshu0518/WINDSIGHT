# syntax=docker/dockerfile:1
# WindSight web UI - static Vite build served by nginx.
#
#   docker build -t windsight-web frontend
#   docker run --rm -p 8080:80 windsight-web
#
# The API origin is baked in at build time (default http://localhost:8000,
# which is correct when the backend publishes port 8000 on the same host):
#
#   docker build --build-arg VITE_API_BASE_URL=http://localhost:8000 \
#     -t windsight-web frontend

FROM node:24-alpine AS build

WORKDIR /app

RUN npm install -g pnpm@11

# Lockfile first so the dependency layer stays cached across source changes.
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN pnpm build

FROM nginx:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
