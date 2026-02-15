FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    cups \
    cups-client \
    libcups2-dev \
    gcc \
    libreoffice-writer \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY printqueue/ printqueue/
COPY templates/ templates/
COPY static/ static/

# Create data directory
RUN mkdir -p data/uploads

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
