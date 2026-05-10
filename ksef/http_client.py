import time

import requests

from config import HTTP_TIMEOUT


class KSeFHttpError(Exception):
    pass


class HttpClient:
    def __init__(self, timeout=HTTP_TIMEOUT):
        self.timeout = timeout

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
                    wait_sec = (
                        int(retry_after)
                        if retry_after and retry_after.isdigit()
                        else min(2**attempt, 30)
                    )
                    print(f"[429] limit API — czekam {wait_sec}s")
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
