from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    retryable: bool = False


def bad_request(code: str, message: str) -> ApiError:
    return ApiError(400, code, message)


def forbidden(
    code: str = "FORBIDDEN", message: str = "You are not allowed to do that."
) -> ApiError:
    return ApiError(403, code, message)


def not_found(message: str = "The requested resource was not found.") -> ApiError:
    return ApiError(404, "NOT_FOUND", message)


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


def unprocessable(code: str, message: str) -> ApiError:
    return ApiError(422, code, message)


def budget_exceeded() -> ApiError:
    return ApiError(429, "BUDGET_EXCEEDED", "The workspace fixture budget is exhausted.")
