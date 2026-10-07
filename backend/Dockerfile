FROM python:3.11-slim

WORKDIR /app

# aria2c enables Turbo Mode multi-connection downloads.
# Local install: Windows: `winget install aria2` or `choco install aria2`;
# macOS: `brew install aria2`; Linux: `sudo apt install aria2`.
RUN apt-get update && apt-get install -y ffmpeg aria2 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
