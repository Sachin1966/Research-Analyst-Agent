# Use official Python lightweight base image
FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Environment variable for port defaults to 7860 (Hugging Face default) or 8000
ENV PORT=7860

EXPOSE 7860

# Run FastAPI app with Uvicorn
CMD uvicorn backend:app --host 0.0.0.0 --port $PORT
