# Python for the harness, Node for the Claude Code CLI that makes the model calls.
FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -q -r /tmp/requirements.txt \
 && npm install -g --silent @anthropic-ai/claude-code
ENV PATH=/venv/bin:$PATH
WORKDIR /eval
