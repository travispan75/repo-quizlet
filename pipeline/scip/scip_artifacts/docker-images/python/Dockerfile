FROM python:3.11-slim

RUN apt-get update && apt-get install -y nodejs npm && apt-get clean

RUN npm install -g @sourcegraph/scip-python

WORKDIR /workspace
