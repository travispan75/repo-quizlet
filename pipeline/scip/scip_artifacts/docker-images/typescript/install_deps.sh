#!/bin/bash
set -e

cp -r /workspace/repo-src /workspace/repo

cd /workspace/repo

if [ -f "package-lock.json" ]; then
    npm ci --quiet || true
elif [ -f "yarn.lock" ]; then
    npm install -g yarn --quiet && yarn install --frozen-lockfile --quiet || true
elif [ -f "pnpm-lock.yaml" ]; then
    npm install -g pnpm --quiet && pnpm install --frozen-lockfile --quiet || true
elif [ -f "package.json" ]; then
    npm install --quiet || true
fi

exec "$@"
