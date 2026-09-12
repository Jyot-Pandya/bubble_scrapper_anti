"""
Observability and performance metrics collector as defined in Section 19.
"""

import time
import math
from collections import defaultdict, deque
from typing import Dict, Any, List


class MetricsCollector:
    def __init__(self, latency_window_size: int = 1000):
        self.latency_window_size = latency_window_size
        self.start_time = time.time()

        self.total_requests: int = 0
        self.total_successes: int = 0
        self.total_failures: int = 0

        self.requests_by_stage: Dict[str, int] = defaultdict(int)
        self.success_by_stage: Dict[str, int] = defaultdict(int)
        self.errors_by_code: Dict[str, int] = defaultdict(int)

        self.total_bytes_downloaded: int = 0
        self.total_images_discovered: int = 0
        self.total_screenshots_captured: int = 0
        self.browser_crashes: int = 0

        self._latencies: deque = deque(maxlen=latency_window_size)

    def record_request(
        self,
        stage: str,
        success: bool,
        duration_ms: int,
        error_code: str = None,
        bytes_count: int = 0,
        images_count: int = 0,
        screenshot_captured: bool = False,
    ):
        self.total_requests += 1
        if success:
            self.total_successes += 1
            self.success_by_stage[stage] += 1
        else:
            self.total_failures += 1

        self.requests_by_stage[stage] += 1
        if error_code:
            self.errors_by_code[error_code] += 1

        self.total_bytes_downloaded += bytes_count
        self.total_images_discovered += images_count
        if screenshot_captured:
            self.total_screenshots_captured += 1

        self._latencies.append(duration_ms)

    def record_browser_crash(self):
        self.browser_crashes += 1

    def _percentile(self, values: List[int], p: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(sorted_vals[int(k)])
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return float(d0 + d1)

    def get_metrics(self) -> Dict[str, Any]:
        uptime_seconds = round(time.time() - self.start_time, 1)
        success_rate = (
            round(self.total_successes / self.total_requests, 4)
            if self.total_requests > 0
            else 1.0
        )
        failure_rate = round(1.0 - success_rate, 4)

        latencies_list = list(self._latencies)
        avg_latency = (
            round(sum(latencies_list) / len(latencies_list), 1)
            if latencies_list
            else 0.0
        )
        p50_latency = round(self._percentile(latencies_list, 0.50), 1)
        p95_latency = round(self._percentile(latencies_list, 0.95), 1)

        http_requests = self.requests_by_stage.get("http", 0)
        browser_requests = self.requests_by_stage.get("browser", 0)
        cache_requests = self.requests_by_stage.get("cache", 0)

        http_pct = round(http_requests / self.total_requests * 100, 1) if self.total_requests > 0 else 0.0
        browser_pct = round(browser_requests / self.total_requests * 100, 1) if self.total_requests > 0 else 0.0

        return {
            "uptime_seconds": uptime_seconds,
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "stages": {
                "http_requests": http_requests,
                "browser_requests": browser_requests,
                "cache_requests": cache_requests,
                "http_percentage": http_pct,
                "browser_escalation_percentage": browser_pct,
                "success_by_stage": dict(self.success_by_stage),
            },
            "latencies": {
                "avg_ms": avg_latency,
                "p50_ms": p50_latency,
                "p95_ms": p95_latency,
            },
            "assets": {
                "total_bytes_downloaded": self.total_bytes_downloaded,
                "total_images_discovered": self.total_images_discovered,
                "total_screenshots_captured": self.total_screenshots_captured,
            },
            "errors": {
                "browser_crashes": self.browser_crashes,
                "by_code": dict(self.errors_by_code),
            },
        }


metrics_collector = MetricsCollector()
