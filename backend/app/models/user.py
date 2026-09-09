"""
Minimal user record + an in-memory repository.
Swap `InMemoryUserRepository` for a Supabase/Postgres-backed one in
production without touching route code (same interface).
"""
import uuid
from dataclasses import dataclass, field


@dataclass
class UserRecord:
    id: str
    email: str
    full_name: str
    hashed_password: str


class UserRepository:
    def __init__(self):
        self._by_id: dict[str, UserRecord] = {}
        self._by_email: dict[str, str] = {}  # email -> id

    def create(self, email: str, full_name: str, hashed_password: str) -> UserRecord:
        user_id = str(uuid.uuid4())
        record = UserRecord(id=user_id, email=email, full_name=full_name, hashed_password=hashed_password)
        self._by_id[user_id] = record
        self._by_email[email.lower()] = user_id
        return record

    def get_by_email(self, email: str) -> UserRecord | None:
        user_id = self._by_email.get(email.lower())
        return self._by_id.get(user_id) if user_id else None

    def get_by_id(self, user_id: str) -> UserRecord | None:
        return self._by_id.get(user_id)


_user_repository_singleton = UserRepository()


def get_user_repository() -> UserRepository:
    return _user_repository_singleton
