from __future__ import annotations

import os
import tarfile
from pathlib import Path

import requests
from dotenv import load_dotenv


_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class SupabaseStorage:
    def __init__(self, bucket: str) -> None:
        load_dotenv(_ENV_PATH)
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SECRET_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SECRET_KEY not set")
        self._base = url.rstrip("/")
        self._key = key
        self._bucket = bucket
        self._auth = {
            "Authorization": f"Bearer {self._key}",
            "apikey": self._key,
        }

    def exists(self, remote_key: str) -> bool:
        url = f"{self._base}/storage/v1/object/{self._bucket}/{remote_key}"
        r = requests.head(url, headers=self._auth, timeout=30)
        return r.status_code == 200

    def upload_file(self, remote_key: str, local_path: Path) -> None:
        url = f"{self._base}/storage/v1/object/{self._bucket}/{remote_key}"
        with open(local_path, "rb") as f:
            r = requests.post(
                url,
                headers={
                    **self._auth,
                    "x-upsert": "true",
                    "Content-Type": "application/octet-stream",
                },
                data=f,
                timeout=600,
            )
        r.raise_for_status()

    def download_file(self, remote_key: str, local_path: Path) -> bool:
        url = f"{self._base}/storage/v1/object/{self._bucket}/{remote_key}"
        r = requests.get(url, headers=self._auth, stream=True, timeout=600)
        if r.status_code in (400, 404):
            return False
        r.raise_for_status()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        return True

    def delete_prefix(self, prefix: str) -> int:
        list_url = f"{self._base}/storage/v1/object/list/{self._bucket}"
        r = requests.post(
            list_url,
            headers={**self._auth, "Content-Type": "application/json"},
            json={"prefix": prefix, "limit": 1000},
            timeout=60,
        )
        r.raise_for_status()
        items = r.json() or []
        if not items:
            return 0
        names = [f"{prefix}/{item['name']}" for item in items if item.get("name")]
        if not names:
            return 0
        del_url = f"{self._base}/storage/v1/object/{self._bucket}"
        r = requests.delete(
            del_url,
            headers={**self._auth, "Content-Type": "application/json"},
            json={"prefixes": names},
            timeout=60,
        )
        r.raise_for_status()
        return len(names)


def make_tarball(
    src_dir: Path,
    dest_tar: Path,
    exclude_names: frozenset[str] | None = None,
) -> None:
    dest_tar.parent.mkdir(parents=True, exist_ok=True)
    excl = exclude_names or frozenset()

    def _filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        # `info.name` is the in-archive path; any path component matching
        # an exclude is dropped (file or directory).
        parts = Path(info.name).parts
        if any(part in excl for part in parts):
            return None
        return info

    with tarfile.open(dest_tar, "w:gz") as tar:
        tar.add(src_dir, arcname=src_dir.name, filter=_filter)


def extract_tarball(tar_path: Path, dest_parent: Path) -> None:
    dest_parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(dest_parent)
