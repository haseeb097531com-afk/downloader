"""Live download progress over WebSocket.

The Celery workers publish progress snapshots to Redis; this endpoint relays them
to the browser so the queue and library screens update without polling. It closes
the gap left by the progress channel the frontend already opens in
``frontend/lib/store/profiles.ts``.

Connections are multiplexed: every message on the socket is tagged with its
``download_id``, so one socket per download is not required.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.redis_client import listen_progress

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Progress"])


@router.websocket("/ws/progress")
async def progress_socket(
    websocket: WebSocket,
    download_id: Optional[str] = Query(
        None, description="Watch one download; omit to receive every download's progress"
    ),
) -> None:
    """Stream download progress to a WebSocket client.

    On connect the latest snapshot for ``download_id`` (if any) is sent immediately,
    so a client that joins mid-download does not have to wait for the next chunk.

    Args:
        websocket: The accepted WebSocket connection.
        download_id: Restrict the stream to a single download, or ``None`` for all.

    Raises:
        WebSocketDisconnect: Handled internally to close the stream cleanly.
    """
    await websocket.accept()

    stop = asyncio.Event()
    reader = asyncio.create_task(_relay_progress(websocket, download_id, stop))

    try:
        # The client is not expected to send anything; this loop exists only to
        # detect the disconnect and to keep the receive buffer drained.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - transport level failures
        logger.warning("Progress socket for %s ended: %s", download_id or "all", exc)
    finally:
        stop.set()
        reader.cancel()
        try:
            await reader
        except (asyncio.CancelledError, WebSocketDisconnect):
            pass
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Error closing progress relay: %s", exc)


async def _relay_progress(websocket: WebSocket, download_id: Optional[str], stop: asyncio.Event) -> None:
    """Forward Redis progress snapshots to the socket until ``stop`` is set."""
    try:
        async for payload in listen_progress(download_id=download_id, stop=stop):
            await websocket.send_json(payload)
    except asyncio.CancelledError:
        raise
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        # A Redis outage must not surface as an opaque protocol error; tell the
        # client the stream is degraded and close cleanly.
        logger.warning("Progress relay for %s stopped: %s", download_id or "all", exc)
        try:
            await websocket.send_json({"status": "error", "error": "Progress stream unavailable"})
        except Exception:
            pass