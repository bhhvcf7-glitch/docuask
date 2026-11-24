from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, get_resources, get_session
from app.core.config import Settings, get_settings
from app.core.resources import AppResources
from app.db.models import Chunk, User
from app.db.repositories import get_document, list_documents
from app.schemas.documents import DocumentPublic
from app.services.document_lifecycle import (
    DocumentBusy,
    DocumentNotFound,
    DocumentNotRetryable,
    FileCleanupFailed,
    VectorCleanupFailed,
    delete_document,
    retry_document,
    stored_path,
)
from app.services.documents import (
    DuplicateDocument,
    InvalidUpload,
    UploadTooLarge,
    save_document,
)
from app.services.ingestion import ingest_document
from app.services.viewer import render_page

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=201, response_model=DocumentPublic)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    resources: Annotated[AppResources, Depends(get_resources)],
) -> DocumentPublic:
    owner_id = user.id
    try:
        document = await save_document(
            session,
            user_id=owner_id,
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

    background_tasks.add_task(
        ingest_document, document.id, owner_id, settings,
        resources.embeddings, resources.index, resources.sessions,
    )
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


@router.post("/{document_id}/retry", response_model=DocumentPublic, status_code=202)
async def retry_failed_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    resources: Annotated[AppResources, Depends(get_resources)],
) -> DocumentPublic:
    try:
        document = await retry_document(
            session, user_id=user.id, document_id=document_id,
            settings=settings, index=resources.index,
        )
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except DocumentNotRetryable as exc:
        raise HTTPException(status_code=409, detail="Only failed documents can be retried") from exc
    except (VectorCleanupFailed, FileCleanupFailed) as exc:
        raise HTTPException(status_code=503, detail="Document retry is unavailable") from exc

    background_tasks.add_task(
        ingest_document, document.id, user.id, settings,
        resources.embeddings, resources.index, resources.sessions,
    )
    return DocumentPublic.model_validate(document)


@router.delete("/{document_id}", status_code=204)
async def remove_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    resources: Annotated[AppResources, Depends(get_resources)],
) -> None:
    try:
        await delete_document(
            session, user_id=user.id, document_id=document_id,
            settings=settings, index=resources.index,
        )
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except DocumentBusy as exc:
        raise HTTPException(status_code=409, detail="Document is still processing") from exc
    except (VectorCleanupFailed, FileCleanupFailed) as exc:
        raise HTTPException(status_code=503, detail="Document cleanup is incomplete") from exc


@router.get("/{document_id}/pdf")
async def original_pdf(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    document = await get_document(session, user_id=user.id, document_id=document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    path = stored_path(settings, user.id, document)
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(
        path, media_type="application/pdf", filename=document.original_name,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{document_id}/pages/{number}")
async def view_page(
    document_id: UUID,
    number: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    chunk_id: UUID | None = None,
):
    document = await get_document(session, user_id=user.id, document_id=document_id)
    if document is None or document.status != "ready":
        raise HTTPException(404, "Document not found")
    path = stored_path(settings, user.id, document)
    passage = None
    if chunk_id is not None:
        chunk = await session.scalar(select(Chunk).where(
            Chunk.id == chunk_id, Chunk.user_id == user.id,
            Chunk.document_id == document_id, Chunk.page_number == number,
        ))
        if chunk is None:
            raise HTTPException(404, "Source not found")
        passage = chunk.original_text
    try:
        result = await run_in_threadpool(render_page, path, number, passage)
    except (IndexError, OSError) as exc:
        raise HTTPException(404, "Page not found") from exc
    return JSONResponse(result, headers={"Cache-Control": "no-store"})
