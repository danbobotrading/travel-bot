FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port for Choreo health checks
EXPOSE 8080

# Run the application
CMD ["python", "bot.py"]
