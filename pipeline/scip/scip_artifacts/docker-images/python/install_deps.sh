#!/bin/bash
set -e

cp -r /workspace/repo-src /workspace/repo

cd /workspace/repo

if [ -f "pyproject.toml" ]; then
    pip install -e . --quiet || true
fi

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet || true
fi

if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt --quiet || true
fi

if [ -f "setup.py" ]; then
    pip install -e . --quiet || true
fi

if [ -f "setup.cfg" ]; then
    pip install -e . --quiet || true
fi

if [ -f "Pipfile" ]; then
    pip install pipenv --quiet && pipenv install --system --deploy --ignore-pipfile --quiet || true
fi

exec "$@"
