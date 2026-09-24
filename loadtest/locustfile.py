import os

from locust import HttpUser, between, task


class SportyReadinessUser(HttpUser):
    """Low-risk API load profile for liveness and readiness checks."""

    wait_time = between(0.1, 0.5)
    host = os.getenv("LOADTEST_HOST", "http://127.0.0.1:8000")

    def on_start(self) -> None:
        self.api_key = os.getenv("LOADTEST_API_KEY", "")
        self.headers = {"X-API-Key": self.api_key} if self.api_key else {}

    @task(3)
    def health(self) -> None:
        self.client.get("/api/v1/health", name="GET /api/v1/health", headers=self.headers)

    @task(1)
    def readiness(self) -> None:
        self.client.get("/api/v1/ready", name="GET /api/v1/ready", headers=self.headers)
