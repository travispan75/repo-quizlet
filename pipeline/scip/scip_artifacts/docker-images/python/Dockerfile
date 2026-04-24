FROM python:3.11-slim

RUN apt-get update && apt-get install -y nodejs npm && apt-get clean

RUN npm install -g @sourcegraph/scip-python

COPY install_deps.sh /install_deps.sh
RUN chmod +x /install_deps.sh

WORKDIR /workspace

ENTRYPOINT ["/install_deps.sh"]
