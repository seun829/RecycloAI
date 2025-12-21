FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app
COPY . .

# Spaces uses 7860 by default
EXPOSE 7860

# Run with gunicorn (recommended for production)
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
