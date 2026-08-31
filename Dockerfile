FROM node:20-bookworm AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY frontend /app/frontend
COPY backend /app/backend
COPY data ./data
COPY --from=frontend /app/frontend/dist ./frontend/dist

ENV MONGO_URI=mongodb://mongo:27017
ENV MONGO_DB=inventory_management
ENV DOCUMENTS_DIR=/app/generated-documents
ENV CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
