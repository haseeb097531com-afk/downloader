import asyncio
import tempfile
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.models.base import Base
from app.models.download import Download, DownloadStatus
from app.services.processor.pipeline import ProcessingPipeline
from app.core.config import settings

async def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        download_dir = Path(tmpdir) / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        platform_dir = download_dir / "youtube"
        platform_dir.mkdir(parents=True, exist_ok=True)
        src = platform_dir / "video.mp4"
        src.write_bytes(b"fake video data")
        
        engine = create_async_engine('sqlite+aiosqlite:///:memory:', future=True, connect_args={'check_same_thread': False})
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as db_session:
            # Monkeypatch like the test
            old_categorize = settings.AUTO_CATEGORIZE
            settings.AUTO_CATEGORIZE = True
            settings.AUTO_MERGE = False
            settings.EMBED_METADATA = False
            settings.GENERATE_THUMBNAILS = False
            settings.DOWNLOAD_DIR = str(download_dir)
            
            try:
                download = Download(
                    url="https://youtube.com/watch?v=abc123",
                    platform="youtube",
                    content_type="video",
                    title="Epic gaming highlights",
                    file_path=str(src),
                    status=DownloadStatus.COMPLETED,
                    metadata_json={"uploader_name": "Gamer123", "description": "Best gaming moments", "tags": ["gaming"]},
                )
                db_session.add(download)
                await db_session.commit()
                await db_session.refresh(download)
                print('Before pipeline:', download.category)
                
                pipeline = ProcessingPipeline(db_session=db_session)
                print('Pipeline created, AUTO_CATEGORIZE:', settings.AUTO_CATEGORIZE)
                await pipeline.process_download(download.id)
                
                # Check what categorizer returns
                from app.services.ai.categorizer import ContentCategorizer
                cat = ContentCategorizer()
                res = cat.categorize(title='Epic gaming highlights', description='Best gaming moments', tags=['gaming'])
                print('Categorizer result:', res)
                
                await db_session.refresh(download)
                print('After pipeline:', download.category)
                print('file_path:', download.file_path)
            finally:
                settings.AUTO_CATEGORIZE = old_categorize
        await engine.dispose()

asyncio.run(main())
