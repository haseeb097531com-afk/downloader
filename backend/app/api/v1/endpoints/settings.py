from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps_auth import get_current_user, require_role
from app.core.settings_service import SettingsService
from app.models.user import UserRole
from app.schemas.settings import ProcessingSettings

router = APIRouter(tags=["Settings"])


def get_settings_service() -> SettingsService:
    return SettingsService()


@router.get("/settings", response_model=ProcessingSettings)
async def read_settings(
    current_user: User = Depends(require_role(UserRole.OWNER)),
    service: SettingsService = Depends(get_settings_service),
) -> ProcessingSettings:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner can view global settings",
        )
    data = service.get_settings()
    return ProcessingSettings(**data)


@router.put("/settings", response_model=ProcessingSettings)
async def update_settings(
    payload: ProcessingSettings,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    service: SettingsService = Depends(get_settings_service),
) -> ProcessingSettings:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner can modify global settings",
        )
    data = service.update_settings(payload.model_dump(exclude_unset=True))
    return ProcessingSettings(**data)
