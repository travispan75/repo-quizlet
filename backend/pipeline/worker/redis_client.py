import json
import os
from pathlib import Path

from dotenv import load_dotenv
from upstash_redis import Redis


_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class RedisClient:
    def __init__(self) -> None:
        load_dotenv(_ENV_PATH)
        url = os.environ.get("UPSTASH_REDIS_REST_URL")
        token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
        if not url or not token:
            raise RuntimeError(
                "UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN not set"
            )
        self.client = Redis(url=url, token=token)

    def enqueue(self, queue: str, payload: str) -> None:
        self.client.lpush(queue, payload)

    def dequeue_reliable(
        self,
        queue: str,
        processing: str,
    ) -> str | None:
        return self.client.lmove(queue, processing, "RIGHT", "LEFT")

    def ack(self, processing: str, payload: str) -> None:
        self.client.lrem(processing, 1, payload)

    def retry(
        self,
        processing: str,
        queue: str,
        old_payload: str,
        new_payload: str,
    ) -> None:
        self.client.lrem(processing, 1, old_payload)
        self.client.lpush(queue, new_payload)

    def recover_in_flight(self, queue: str, processing: str) -> int:
        count = 0
        while True:
            moved = self.client.lmove(processing, queue, "RIGHT", "RIGHT")
            if moved is None:
                break
            count += 1
        return count

    def set_json(self, key: str, value: dict, ex: int | None = None) -> None:
        self.client.set(key, json.dumps(value), ex=ex)
