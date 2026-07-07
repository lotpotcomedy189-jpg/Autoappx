FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    aria2 \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# (Optional) Install yt-dlp if not already in requirements
RUN pip install yt-dlp

# Copy requirements and install Python packages
COPY master.txt /app/requirements.txt
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port (optional, for web server)
EXPOSE 5000

# Start the bot
CMD ["python3", "main.py"]
