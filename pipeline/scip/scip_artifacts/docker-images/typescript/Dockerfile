FROM node:20-slim

RUN npm install -g @sourcegraph/scip-typescript

COPY install_deps.sh /install_deps.sh
RUN chmod +x /install_deps.sh

WORKDIR /workspace

ENTRYPOINT ["/install_deps.sh"]
