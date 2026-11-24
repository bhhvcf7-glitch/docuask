from sqlalchemy import ForeignKeyConstraint

from app.db.models import Base


def test_current_schema_tables_are_defined() -> None:
    assert set(Base.metadata.tables) == {
        "users", "documents", "chunks", "conversations", "conversation_turns"
    }


def test_chunks_cannot_reference_a_document_owned_by_another_user() -> None:
    constraints = [
        item for item in Base.metadata.tables["chunks"].constraints
        if isinstance(item, ForeignKeyConstraint)
    ]

    assert len(constraints) == 1
    fk = constraints[0]
    assert [item.parent.name for item in fk.elements] == ["document_id", "user_id"]
    assert [item.column.name for item in fk.elements] == ["id", "user_id"]
    assert fk.ondelete == "CASCADE"
