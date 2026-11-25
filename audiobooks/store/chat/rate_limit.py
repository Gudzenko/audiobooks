import fcntl
import json
import time
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings


class ChatRateLimitExceeded(Exception):
    pass


class ChatRequestInProgress(Exception):
    pass


@contextmanager
def limit_chat_requests(user_id: int):
    state_path = _state_path(user_id)
    state_path.touch(mode=0o600, exist_ok=True)
    with state_path.open("r+", encoding="utf-8") as state_file:
        try:
            fcntl.flock(state_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ChatRequestInProgress from error
        state = _read_state(state_file)
        now = time.time()
        window_started = state.get("window_started", 0)
        request_count = state.get("request_count", 0)
        if now - window_started >= 60:
            window_started = now
            request_count = 0
        if request_count >= settings.CHAT_REQUESTS_PER_MINUTE:
            raise ChatRateLimitExceeded
        _write_state(
            state_file,
            {
                "window_started": window_started,
                "request_count": request_count + 1,
            },
        )
        yield


def _state_path(user_id: int) -> Path:
    directory = Path(settings.CHAT_RATE_LIMIT_DIR)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory / f"user-{user_id}.json"


def _read_state(state_file) -> dict:
    state_file.seek(0)
    try:
        value = json.load(state_file)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_state(state_file, state: dict) -> None:
    state_file.seek(0)
    json.dump(state, state_file)
    state_file.truncate()
    state_file.flush()
