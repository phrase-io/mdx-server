#!/usr/bin/env python3
"""
Simple load tester for the mdx-server API.

Example:
    python load_test.py --url http://localhost:8000/api/entry/god \
        --requests 200 --concurrency 20
"""
import argparse
import asyncio
import statistics
import time

import aiohttp


def _percentile(data, pct):
    if not data:
        return 0.0
    k = (len(data) - 1) * pct / 100
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[int(k)]
    d0 = data[f] * (c - k)
    d1 = data[c] * (k - f)
    return d0 + d1


async def worker(session, url, request_count, results):
    for _ in range(request_count):
        start = time.perf_counter()
        try:
            async with session.get(url) as resp:
                await resp.read()
                elapsed = (time.perf_counter() - start) * 1000
                results.append((True, elapsed))
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            results.append((False, elapsed))


async def run_load_test(url, total_requests, concurrency):
    per_worker = total_requests // concurrency
    remainder = total_requests % concurrency
    tasks = []
    results = []
    conn = aiohttp.TCPConnector(limit=concurrency)
    timeout = aiohttp.ClientTimeout(total=None)
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        for i in range(concurrency):
            count = per_worker + (1 if i < remainder else 0)
            if count:
                tasks.append(asyncio.create_task(worker(session, url, count, results)))
        start = time.perf_counter()
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start
    return results, total_time


def print_report(results, total_time, total_requests):
    latencies = [lat for success, lat in results if success]
    failures = sum(1 for success, _ in results if not success)
    success = total_requests - failures
    qps = total_requests / total_time if total_time else 0
    print("\n=== Load Test Report ===")
    print(f"Total requests: {total_requests}")
    print(f"Total time: {total_time:.2f} s")
    print(f"Success: {success}, Failures: {failures}")
    print(f"Requests/sec: {qps:.2f}")
    if not latencies:
        print("No successful requests to compute latency stats.")
        return
    latencies.sort()
    print("Latency (ms):")
    print(f"  Min: {latencies[0]:.2f}")
    print(f"  Avg: {statistics.mean(latencies):.2f}")
    print(f"  P50: {_percentile(latencies, 50):.2f}")
    print(f"  P90: {_percentile(latencies, 90):.2f}")
    print(f"  P99: {_percentile(latencies, 99):.2f}")
    print(f"  Max: {latencies[-1]:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Simple load tester for mdx-server.")
    parser.add_argument("--url", default="http://localhost:8000/api/entry/god",
                        help="Target URL to test")
    parser.add_argument("--requests", type=int, default=100,
                        help="Total number of requests to send")
    parser.add_argument("--concurrency", type=int, default=10,
                        help="Number of concurrent workers")
    args = parser.parse_args()
    if args.requests <= 0 or args.concurrency <= 0:
        parser.error("requests and concurrency must be positive integers")
    print(f"Target: {args.url}")
    print(f"Requests: {args.requests}  Concurrency: {args.concurrency}")
    results, total_time = asyncio.run(
        run_load_test(args.url, args.requests, args.concurrency)
    )
    print_report(results, total_time, args.requests)


if __name__ == "__main__":
    main()
