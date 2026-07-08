"""Lightweight Redis-backed job queue for SUMO scenario runs.

The synchronous `/run-scenario` endpoint (spec section O) is fine for short
MVP simulations, but the spec explicitly says: "For production, use Redis
queue + worker and return job status." This module provides that path
without pulling in Celery/Dramatiq: a Redis list acts as the queue, and a
Redis hash per job holds status/result JSON.

Usage:
    enqueue_scenario_job(scenario_config) -> job_id
    worker_loop() -- run this in a separate process/thread; it blocks on
        BLPOP and executes jobs one at a time via SumoScenarioRunner.
    get_job_status(job_id) -> dict
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import redis

from app.config import get_simulation_settings
from app.scenario_runner import SumoScenarioRunner

logger = logging.getLogger(__name__)

QUEUE_KEY = "sumo:scenario_jobs"
JOB_KEY_PREFIX = "sumo:job:"
JOB_TTL_SECONDS = 60 * 60 * 24  # 1 day


def _redis_client() -> redis.Redis:
    settings = get_simulation_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def enqueue_scenario_job(scenario_config: dict[str, Any]) -> str:
    job_id = scenario_config.get("run_id") or str(uuid.uuid4())
    scenario_config = {**scenario_config, "run_id": job_id}
    client = _redis_client()
    client.hset(
        f"{JOB_KEY_PREFIX}{job_id}",
        mapping={"status": "queued", "scenario_config": json.dumps(scenario_config), "result": ""},
    )
    client.expire(f"{JOB_KEY_PREFIX}{job_id}", JOB_TTL_SECONDS)
    client.rpush(QUEUE_KEY, job_id)
    return job_id


def get_job_status(job_id: str) -> dict[str, Any] | None:
    client = _redis_client()
    data = client.hgetall(f"{JOB_KEY_PREFIX}{job_id}")
    if not data:
        return None
    result = json.loads(data["result"]) if data.get("result") else None
    return {"job_id": job_id, "status": data.get("status"), "result": result}


def _process_one(client: redis.Redis, runner: SumoScenarioRunner, job_id: str) -> None:
    key = f"{JOB_KEY_PREFIX}{job_id}"
    raw = client.hget(key, "scenario_config")
    if raw is None:
        logger.warning("Job %s has no scenario_config, skipping", job_id)
        return
    scenario_config = json.loads(raw)
    client.hset(key, "status", "running")
    try:
        result = runner.run_scenario(scenario_config)
        client.hset(key, mapping={"status": result.get("status", "failed"), "result": json.dumps(result)})
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Scenario job %s failed", job_id)
        client.hset(key, mapping={"status": "failed", "result": json.dumps({"error": str(exc)})})


def worker_loop(poll_timeout_seconds: int = 5) -> None:  # pragma: no cover - long running
    settings = get_simulation_settings()
    client = _redis_client()
    runner = SumoScenarioRunner(
        base_scenario_dir=settings.sumo_scenario_dir,
        runs_dir=settings.sumo_runs_dir,
        sumo_binary=settings.sumo_binary,
    )
    logger.info("SUMO scenario queue worker started, listening on %s", QUEUE_KEY)
    while True:
        item = client.blpop([QUEUE_KEY], timeout=poll_timeout_seconds)
        if item is None:
            continue
        _, job_id = item
        _process_one(client, runner, job_id)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    worker_loop()
