"""Prueba de carga: 5 POST /tasks concurrentes."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class JobResult:
    job_id: str
    post_ms: float
    total_ms: float
    final_status: str
    approved: bool


async def _wait_job(
    client: httpx.AsyncClient,
    job_id: str,
    *,
    timeout_s: float,
    auto_approve: bool,
) -> JobResult:
    deadline = time.perf_counter() + timeout_s
    approved = False

    while time.perf_counter() < deadline:
        response = await client.get(f"/tasks/{job_id}")
        response.raise_for_status()
        body = response.json()
        status = body.get("status")

        if status == "AWAITING_APPROVAL" and auto_approve:
            approve = await client.post(
                f"/tasks/{job_id}/approve",
                json={"approved": True},
            )
            approve.raise_for_status()
            approved = True
        elif status in {"DONE", "FAILED"}:
            return JobResult(
                job_id=job_id,
                post_ms=0.0,
                total_ms=0.0,
                final_status=status,
                approved=approved,
            )

        await asyncio.sleep(0.15)

    raise TimeoutError(f"timeout waiting job {job_id}")


async def _submit_and_track(
    client: httpx.AsyncClient,
    index: int,
    *,
    timeout_s: float,
    auto_approve: bool,
) -> JobResult:
    payload = {"task": f"Carga concurrente #{index + 1}: analizar APIs async"}
    started = time.perf_counter()
    post = await client.post("/tasks", json=payload)
    post.raise_for_status()
    post_ms = (time.perf_counter() - started) * 1000
    job_id = post.json()["job_id"]

    result = await _wait_job(
        client,
        job_id,
        timeout_s=timeout_s,
        auto_approve=auto_approve,
    )
    total_ms = (time.perf_counter() - started) * 1000
    result.post_ms = post_ms
    result.total_ms = total_ms
    return result


async def run_load_test(
    base_url: str,
    *,
    concurrency: int,
    timeout_s: float,
    auto_approve: bool,
) -> list[JobResult]:
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        health = await client.get("/health")
        health.raise_for_status()
        print("health", health.json())

        tasks = [
            _submit_and_track(
                client,
                i,
                timeout_s=timeout_s,
                auto_approve=auto_approve,
            )
            for i in range(concurrency)
        ]
        return await asyncio.gather(*tasks)


def _print_summary(results: list[JobResult]) -> None:
    post_times = [r.post_ms for r in results]
    total_times = [r.total_ms for r in results]
    statuses = {r.final_status for r in results}

    print("\n=== Resumen ===")
    print(f"jobs: {len(results)}")
    print(f"statuses: {', '.join(sorted(statuses))}")
    print(f"POST p50: {statistics.median(post_times):.1f} ms")
    print(f"POST p95: {sorted(post_times)[max(0, int(len(post_times) * 0.95) - 1)]:.1f} ms")
    print(f"total p50: {statistics.median(total_times):.1f} ms")
    print(f"total p95: {sorted(total_times)[max(0, int(len(total_times) * 0.95) - 1)]:.1f} ms")

    for result in results:
        print(
            f"- {result.job_id[:8]}… post={result.post_ms:.0f}ms "
            f"total={result.total_ms:.0f}ms status={result.final_status} "
            f"approved={result.approved}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="5 requests concurrentes a POST /tasks")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--no-auto-approve", action="store_true")
    args = parser.parse_args()

    results = asyncio.run(
        run_load_test(
            args.base_url,
            concurrency=args.concurrency,
            timeout_s=args.timeout,
            auto_approve=not args.no_auto_approve,
        )
    )
    _print_summary(results)

    failed = [r for r in results if r.final_status != "DONE"]
    if failed:
        raise SystemExit(f"{len(failed)} jobs no terminaron en DONE")

    print("\nALL OK")


if __name__ == "__main__":
    main()
