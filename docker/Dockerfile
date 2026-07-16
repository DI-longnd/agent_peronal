# Multi-stage: build web tĩnh bằng node, image chạy chỉ là python-slim.
# KHÔNG cài playwright — browser automation chạy trên máy khách (PLAN.md v2);
# server chỉ import BROWSER_TOOL_SPECS (dict thuần, Phase 0.3 đảm bảo).
FROM node:20-slim AS web
WORKDIR /build
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY agent-framework/ agent-framework/
COPY server/ server/
COPY --from=web /build/dist web/dist
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" openai pyyaml python-dotenv markdownify
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
