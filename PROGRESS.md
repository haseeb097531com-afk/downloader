# DIAGNOSTIC REPORT — 2026-10-07T12:31:10Z

---

## 1. BACKEND FILES

**D:\new downloader\backend** — top 2 levels:
```
d----- alembic
d----- app
d----- data
d----- downloads
d----- tests
d----- testserver
d----- venv
d----- __pycache__
-a---- .env.example
-a---- alembic.ini
-a---- celery_worker.py
-a---- check_alembic.py
-a---- check_db.py
-a---- check_db2.py
-a---- check_home.py
-a---- check_models.py
-a---- cleanup_alembic.py
-a---- conftest.py
-a---- debug_pipeline.py
-a---- debug_routes.py
-a---- Dockerfile
-a---- main.py
-a---- mediavault.db
-a---- pytest.ini
-a---- requirements.txt
-a---- requirements_fixed.txt
-a---- uvicorn.log
-a---- verify_migration.py
```

**app/** subdirs: api, core, db, desktop, models, plugins, schemas, services, workers

**FastAPI app creation** — `D:\new downloader\backend\app\main.py:38-42`:
```python
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
)
```

---

## 2. VENV + DEPS

**venv exists**: YES (`D:\new downloader\backend\venv`)

**venv\Scripts\python.exe exists**: YES

**pip list** — key packages:
| Package | Version | Status |
|---------|---------|--------|
| fastapi | 0.142.2 | PRESENT |
| uvicorn | 0.54.0 | PRESENT |
| celery | 5.6.3 | PRESENT |
| redis | 8.1.0 | PRESENT |
| yt-dlp | 2026.8.19 | PRESENT |
| sqlalchemy | 2.1.3 | PRESENT |
| alembic | 1.20.0 | PRESENT |

**MISSING from key list**: NONE

---

## 3. EXTERNAL BINARIES

| Binary | `where.exe` | `--version` | Status |
|--------|-------------|-------------|--------|
| ffmpeg | `Could not find files` | `not recognized` | **MISSING** |
| yt-dlp | `Could not find files` | `not recognized` | **MISSING** |

Neither `ffmpeg` nor `yt-dlp` is on system PATH.

---

## 4. REDIS + CELERY

**Redis port 6379**:
```
Get-NetTCPConnection -LocalPort 6379  →  NO OUTPUT (nothing listening)
```

**Celery worker processes**:
```
tasklist | findstr celery/python  →  3 python.exe processes (PIDs 16840, 16032, 7212)
No process named "celery" found. Celery worker NOT confirmed running.
```

---

## 5. THE ACTUAL ERROR

**Backend running on :8000**? YES — PID 7212 listening on `0.0.0.0:8000`.

**GET /docs**:
```
Invoke-WebRequest http://127.0.0.1:8000/docs  →  TIMEOUT (30s)
```

**POST /downloads** for `https://www.youtube.com/watch?v=jNQXAC9IVRw`:
> **NOT TESTED** — /docs already times out; backend appears unresponsive to HTTP. Cannot test download endpoint.

---

## 6. CONFIG

**Source**: `D:\new downloader\backend\app\core\config.py` (lines 14-166)

| Setting | Value |
|---------|-------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./mediavault.db` (from env default) |
| `REDIS_URL` | `redis://localhost:6379/0` (from env default) |
| `DOWNLOAD_DIR` | `./downloads` (from env default) |
| `AUTH_ENABLED` | **False** (line 166: `AUTH_ENABLED: bool = False`) |

No `.env` file found in backend root; only `.env.example` exists.

---

I changed nothing; here is the truth.