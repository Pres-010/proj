# Use an official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements (use your existing requirement.txt)
COPY requirement.txt ./requirement.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirement.txt

# Copy project files
COPY . .

# Ensure database folder exists and is writable
RUN mkdir -p database && touch database/data.db

# Default environment variable placeholder (override at runtime)
ENV GOOGLE_API_KEY=""

# Run the agent script
CMD ["python", "main.py"]
