# Architecture Overview

MediaVault Pro uses a monorepo architecture separating frontend and backend workspaces.

## Frontend (Next.js 14)
- **App Router**: Organizes routes with nested layouts (dashboard, queue, library).
- **State Management**: Zustand for global state, React Hook Form for local form state.
- **Styling**: Tailwind CSS + Shadcn UI for a scalable, customizable component system.

## Backend (FastAPI + Celery)
- **FastAPI**: Serves RESTful API endpoints for the frontend.
- **Celery & Redis**: Manages background asynchronous tasks (downloading, processing).
- **yt-dlp**: Core extraction engine for media across platforms.
- **SQLite/SQLAlchemy**: Local database storage for user settings, queue, and library metadata.
- **AI Modules**: Plug-and-play architecture for faster-whisper and imagehash integration.
