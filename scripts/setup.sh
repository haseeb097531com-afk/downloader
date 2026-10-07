#!/bin/bash
# setup.sh

echo "Starting MediaVault Setup..."

if ! command -v node &> /dev/null; then echo "Node.js is not installed. Please install Node.js."; exit 1; fi
if ! command -v python &> /dev/null; then echo "Python is not installed. Please install Python."; exit 1; fi
if ! command -v docker &> /dev/null; then echo "Docker is not installed. Please install Docker."; exit 1; fi
if ! command -v ffmpeg &> /dev/null; then echo "FFmpeg is not installed. Please install FFmpeg."; exit 1; fi

echo "Installing frontend dependencies..."
cd frontend && npm install && cd ..

echo "Installing backend dependencies..."
cd backend && python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements.txt && cd ..

echo "Creating .env files..."
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env

echo "Initializing database..."
# SQLAlchemy will create the tables on startup automatically through lifecycle events.

echo "Setup Complete! Run 'make dev' to start the application."
