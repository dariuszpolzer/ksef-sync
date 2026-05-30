from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests

from config import HTTP_TIMEOUT


class KSeFHttpError(Exception):
    pass


@dataclass
class RateLimitMonitor:
    events: list[dict] = field(default_factory=list)

    def record(self, response: requests.Response, wait_seconds: int | None = None) -> None:
        headers = response.headers
        event = {
            "status_code": response.status_code,
            "url": response.url,
            "retry_after": headers.get("Retry-After"),
            "wait_seconds": wait_seconds,
            "limit": headers.get("X-RateLimit-Limit"),
            "remaining": headers.get("X-RateLimit-Remaining"),
            "reset": headers.get("X-RateLimit-Reset"),
        }
        self.events.append(event)

    @property
    def last_event(self) -> dict | None:
        return self.events[-1] if self.events else None


def parse_retry_after(value: str | None, fallback_seconds: int) -> int:
    if not value:
        return fallback_seconds

    if value.isdigit():
        return max(0, int(value))

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return fallback_seconds

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    return max(0, int((retry_at - now).total_seconds()))


class HttpClient:
    def __init__(self, timeout=HTTP_TIMEOUT, rate_limit_monitor: RateLimitMonitor | None = None):
        self.timeout = timeout
        self.rate_limit_monitor = rate_limit_monitor or RateLimitMonitor()

    def _error_text(self, response: requests.Response) -> str:
        try:
            data = response.json()
            return str(data)
        except Exception:
            return response.text

    def request(self, method, url, headers=None, json_body=None, stream=False, retries=5):
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body,
                    timeout=self.timeout,
                    stream=stream,
                )

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_sec = parse_retry_after(retry_after, min(2**attempt, 30))
                    self.rate_limit_monitor.record(response, wait_sec)
                    print(
                        f"[429] limit API - Retry-After={retry_after or 'brak'}, czekam {wait_sec}s"
                    )
                    time.sleep(wait_sec)
                    continue

                if 500 <= response.status_code < 600:
                    wait_sec = min(2**attempt, 30)
                    print(f"[{response.status_code}] błąd serwera — retry za {wait_sec}s")
                    time.sleep(wait_sec)
                    continue

                if not response.ok:
                    raise KSeFHttpError(
                        f"HTTP {response.status_code}: {self._error_text(response)}"
                    )

                return response

            except requests.RequestException as exc:
                last_error = exc

                if attempt == retries:
                    break

                wait_sec = min(2**attempt, 30)
                print(f"[WARN] {exc} -> retry za {wait_sec}s")
                time.sleep(wait_sec)

            except KSeFHttpError:
                raise

        raise KSeFHttpError(f"Nie udało się wykonać żądania {url}. Ostatni błąd: {last_error}")
