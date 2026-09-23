from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "sporty_http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "sporty_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)
ACTIVE_REQUESTS = Gauge(
    "sporty_http_active_requests",
    "Number of requests currently being processed.",
)
JOBS_TOTAL = Counter(
    "sporty_jobs_total",
    "Prediction jobs by final state.",
    ["job_type", "status"],
)
JOB_DURATION = Histogram(
    "sporty_job_duration_seconds",
    "Prediction job execution duration.",
    ["job_type"],
)
JOB_RETRIES = Counter(
    "sporty_job_retries_total",
    "Prediction job retries.",
    ["job_type"],
)
