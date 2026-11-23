import hashlib
from pathlib import Path
from uuid import UUID, uuid4

import aiofiles
from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.models import Document

READ_SIZE = 64 * 1024


class InvalidUpload(Exception):
    pass


class DuplicateDocument(Exception):
    pass


class UploadTooLarge(Exception):
    pass


def verify_pdf(path: Path) -> None:
    try:
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise InvalidUpload("PDF must contain readable, unencrypted pages")
        for page in reader.pages:
            _ = page.mediabox
    except (PdfReadError, ValueError, KeyError, TypeError, IndexError, OSError) as exc:
        raise InvalidUpload("Malformed or unsupported PDF") from exc


async def save_document(
    session: AsyncSession,
    *,
    user_id: UUID,
    upload: UploadFile,
    storage_dir: Path,
    max_bytes: int,
) -> Document:
    original_name = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not original_name or len(original_name.encode("utf-8")) > 255:
        raise InvalidUpload("Invalid filename")
    if "\x00" in original_name or not original_name.lower().endswith(".pdf"):
        raise InvalidUpload("Only .pdf files are accepted")
    if upload.content_type != "application/pdf":
        raise InvalidUpload("Content type must be application/pdf")

    owner_dir = storage_dir.resolve() / str(user_id)
    await run_in_threadpool(owner_dir.mkdir, parents=True, exist_ok=True, mode=0o700)
    doc_id = uuid4()
    stage = owner_dir / f".{doc_id}.upload"
    final = owner_dir / f"{doc_id}.pdf"

    digest = hashlib.sha256()
    size = 0
    prefix = b""
    try:
        async with aiofiles.open(stage, "xb") as output:
            while chunk := await upload.read(READ_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise UploadTooLarge
                if len(prefix) < 5:
                    prefix = (prefix + chunk)[:5]
                digest.update(chunk)
                await output.write(chunk)
        if prefix != b"%PDF-":
            raise InvalidUpload("Invalid PDF signature")
        await run_in_threadpool(verify_pdf, stage)

        sha256 = digest.hexdigest()
        duplicate = await session.scalar(
            select(Document.id).where(
                Document.user_id == user_id, Document.sha256 == sha256
            )
        )
        if duplicate is not None:
            raise DuplicateDocument

        document = Document(
            id=doc_id,
            user_id=user_id,
            original_name=original_name,
            storage_key=f"{user_id}/{doc_id}.pdf",
            media_type="application/pdf",
            size_bytes=size,
            sha256=sha256,
            status="queued",
        )
        await run_in_threadpool(stage.replace, final)
        session.add(document)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            await run_in_threadpool(final.unlink, missing_ok=True)
            duplicate = await session.scalar(
                select(Document.id).where(
                    Document.user_id == user_id, Document.sha256 == sha256
                )
            )
            if duplicate is not None:
                raise DuplicateDocument from exc
            raise
        await session.refresh(document)
        return document
    finally:
        await upload.close()
        await run_in_threadpool(stage.unlink, missing_ok=True)
