"""
SQLite models for passkey auth: User and WebAuthnCredential.
"""
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)  # username or email
    display_name: Mapped[str] = mapped_column(nullable=False, default="")
    email: Mapped[str | None] = mapped_column(nullable=True, unique=True)  # for allowed-users check

    credentials: Mapped[list["WebAuthnCredential"]] = relationship(
        "WebAuthnCredential", back_populates="user", cascade="all, delete-orphan"
    )

    def to_webauthn_user(self):
        """Return (user_id_bytes, user_name, user_display_name) for webauthn options."""
        return (self.id.to_bytes(8, "big"), self.name, self.display_name or self.name)


class WebAuthnCredential(db.Model):
    __tablename__ = "webauthn_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    credential_id: Mapped[bytes] = mapped_column(db.LargeBinary, nullable=False, unique=True)
    public_key: Mapped[bytes] = mapped_column(db.LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(nullable=False, default=0)

    user: Mapped["User"] = relationship("User", back_populates="credentials")
