from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_session
from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.repositories import get_document, list_documents
from app.schemas.documents import DocumentPublic
from app.services.documents import (
    DuplicateDocument,
    InvalidUpload,
    UploadTooLarge,
    save_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=201, response_model=DocumentPublic)
async def upload_document(
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentPublic:
    try:
        document = await save_document(
            session,
            user_id=user.id,
            upload=file,
            storage_dir=settings.storage_dir,
            max_bytes=settings.max_upload_bytes,
        )
    except InvalidUpload as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail="PDF exceeds upload limit") from exc
    except DuplicateDocument as exc:
        raise HTTPException(status_code=409, detail="Document already uploaded") from exc
    return DocumentPublic.model_validate(document)


@router.get("", response_model=list[DocumentPublic])
async def get_documents(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DocumentPublic]:
    documents = await list_documents(session, user_id=user.id)
    return [DocumentPublic.model_validate(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentPublic)
async def get_document_status(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentPublic:
    document = await get_document(session, user_id=user.id, document_id=document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentPublic.model_validate(document)
