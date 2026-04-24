import json
import time

from pipeline import Pipeline
from pipeline.worker.redis_client import RedisClient

def main():
    client = RedisClient()
    job = client.dequeue_blocking("repo_jobs", 5)
    if job is None:
        return

    payload = json.loads(job.decode("utf-8"))
    job_id = payload["job_id"]
    repo_name = payload["repo_name"]
    repo_path = payload["repo_path"]
    repo_url = payload["repo_url"]
    pipeline = Pipeline()

    try:
        pipeline.run(
            repo_path=repo_path,
            job_id=job_id,
            repo_name=repo_name,
            repo_url=repo_url,
        )
    except Exception as e:
        print(f"worker pipeline failed for {repo_path}: {e}")
        client.enqueue("repo_jobs", json.dumps(payload).encode("utf-8"))
        time.sleep(1)


if __name__ == "__main__":
    main()
