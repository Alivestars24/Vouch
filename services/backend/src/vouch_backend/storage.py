from __future__ import annotations

import hashlib
from typing import Protocol
from uuid import UUID

import httpx

from .config import Settings
from .errors import ApiError, conflict, not_found

MAX_MEDIA_BYTES = 5_000_000
BUCKET = "vouch-media"


class MediaStore(Protocol):
    def upload(self, key: str, body: bytes, content_type: str, access_token: str) -> None: ...
    def download(self, key: str, access_token: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class GuestMediaStore(Protocol):
    def upload(self, key: str, body: bytes, content_type: str) -> None: ...
    def download(self, key: str) -> bytes: ...


def _validate_key(key: str) -> str:
    parts = key.split("/")
    if len(parts) != 4 or parts[3] != "source":
        raise ValueError("Invalid domain media key.")
    if any(str(UUID(value)) != value for value in parts[:3]):
        raise ValueError("Invalid domain media key.")
    return key


def _unavailable() -> ApiError:
    return ApiError(503, "STORAGE_UNAVAILABLE", "Private media storage is unavailable.", True)


class SupabaseMediaStore:
    """Caller-token reads/writes; server cleanup credential is used only for exact-key deletion."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        if not settings.supabase_url or not settings.supabase_publishable_key:
            raise ValueError("Private Storage requires its trusted URL and publishable key.")
        self._base = f"{settings.supabase_url.rstrip('/')}/storage/v1"
        self._publishable_key = settings.supabase_publishable_key
        self._cleanup_key = settings.supabase_secret_key
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        )

    def _headers(self, access_token: str) -> dict[str, str]:
        if not access_token:
            raise ApiError(401, "AUTH_REQUIRED", "Sign in to access private media.")
        return {"apikey": self._publishable_key, "Authorization": f"Bearer {access_token}"}

    @staticmethod
    def _error_status(response: httpx.Response) -> str:
        try:
            payload = response.json()
            return str(payload.get("statusCode", "")) if isinstance(payload, dict) else ""
        except ValueError:
            return ""

    def upload(self, key: str, body: bytes, content_type: str, access_token: str) -> None:
        key = _validate_key(key)
        if len(body) > MAX_MEDIA_BYTES:
            raise ApiError(413, "UPLOAD_TOO_LARGE", "Media exceeds the upload limit.")
        headers = self._headers(access_token)
        headers.update({"Content-Type": content_type, "x-upsert": "false"})
        try:
            with self._client() as client:
                response = client.post(
                    f"{self._base}/object/{BUCKET}/{key}", headers=headers, content=body
                )
            if response.is_success:
                return
            if response.status_code == 409 or self._error_status(response) == "409":
                existing = self.download(key, access_token)
                if hashlib.sha256(existing).digest() == hashlib.sha256(body).digest():
                    return
                raise conflict(
                    "UPLOAD_CONTENT_CONFLICT", "This upload already has different bytes."
                )
            raise _unavailable()
        except httpx.HTTPError:
            raise _unavailable() from None

    def _download(
        self, key: str, headers: dict[str, str], *, missing_ok: bool = False
    ) -> bytes | None:
        try:
            with (
                self._client() as client,
                client.stream(
                    "GET",
                    f"{self._base}/object/authenticated/{BUCKET}/{_validate_key(key)}",
                    headers=headers,
                ) as response,
            ):
                if not response.is_success:
                    response.read()
                    if response.status_code == 404 or self._error_status(response) == "404":
                        if missing_ok:
                            return None
                        raise not_found()
                    raise _unavailable()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_MEDIA_BYTES:
                        raise _unavailable()
                return bytes(body)
        except httpx.HTTPError:
            raise _unavailable() from None

    def download(self, key: str, access_token: str) -> bytes:
        result = self._download(key, self._headers(access_token))
        if result is None:
            raise not_found()
        return result

    def delete(self, key: str) -> None:
        key = _validate_key(key)
        if not self._cleanup_key:
            raise _unavailable()
        headers = {"apikey": self._cleanup_key}
        # Local CLI supplies a legacy JWT. Modern secret keys are gateway API keys, not JWTs.
        if self._cleanup_key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self._cleanup_key}"
        try:
            with self._client() as client:
                response = client.request(
                    "DELETE",
                    f"{self._base}/object/{BUCKET}",
                    headers=headers,
                    json={"prefixes": [key]},
                )
            if not response.is_success:
                raise _unavailable()
            if self._download(key, headers, missing_ok=True) is not None:
                raise _unavailable()
        except httpx.HTTPError:
            raise _unavailable() from None


class SupabaseGuestMediaStore:
    """Exact-key guest reads/writes with a distinct server-only Storage credential."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        if not settings.supabase_url or not settings.guest_storage_key:
            raise ValueError("Guest private Storage requires its trusted URL and guest key.")
        self._base = f"{settings.supabase_url.rstrip('/')}/storage/v1"
        self._key = settings.guest_storage_key
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"apikey": self._key}
        # Local Supabase supplies a legacy service-role JWT. Modern secret keys are API keys.
        if self._key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self._key}"
        return headers

    @staticmethod
    def _error_status(response: httpx.Response) -> str:
        try:
            payload = response.json()
            return str(payload.get("statusCode", "")) if isinstance(payload, dict) else ""
        except ValueError:
            return ""

    def upload(self, key: str, body: bytes, content_type: str) -> None:
        key = _validate_key(key)
        if len(body) > MAX_MEDIA_BYTES:
            raise ApiError(413, "UPLOAD_TOO_LARGE", "Media exceeds the upload limit.")
        headers = self._headers()
        headers.update({"Content-Type": content_type, "x-upsert": "false"})
        try:
            with self._client() as client:
                response = client.post(
                    f"{self._base}/object/{BUCKET}/{key}", headers=headers, content=body
                )
            if response.is_success:
                return
            if response.status_code == 409 or self._error_status(response) == "409":
                if hashlib.sha256(self.download(key)).digest() == hashlib.sha256(body).digest():
                    return
                raise conflict(
                    "UPLOAD_CONTENT_CONFLICT", "This upload already has different bytes."
                )
            raise _unavailable()
        except httpx.HTTPError:
            raise _unavailable() from None

    def download(self, key: str) -> bytes:
        key = _validate_key(key)
        try:
            with (
                self._client() as client,
                client.stream(
                    "GET",
                    f"{self._base}/object/authenticated/{BUCKET}/{key}",
                    headers=self._headers(),
                ) as response,
            ):
                if not response.is_success:
                    response.read()
                    if response.status_code == 404 or self._error_status(response) == "404":
                        raise not_found()
                    raise _unavailable()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_MEDIA_BYTES:
                        raise _unavailable()
                return bytes(body)
        except httpx.HTTPError:
            raise _unavailable() from None
