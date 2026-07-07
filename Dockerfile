FROM python:3.11-slim

# Install system dependencies (ffmpeg, aria2, etc.)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    aria2 \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY master.txt /app/requirements.txt
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire codebase
COPY . .

# 🔥 DELETE ALL .so FILES – they cause the "undefined symbol" error
RUN find /app -name "*.so" -type f -delete

# Expose port (Render expects this)
EXPOSE 5000

# Start the bot
CMD ["python3", "main.py"]
