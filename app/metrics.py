import logfire

JOB_COMPLETED = logfire.metric_counter(
    "sporty.jobs.completed",
    unit="1",
    description="Number of prediction jobs completed successfully.",
)
JOB_FAILED = logfire.metric_counter(
    "sporty.jobs.failed",
    unit="1",
    description="Number of prediction jobs that reached the failed state.",
)
JOB_RETRIES = logfire.metric_counter(
    "sporty.jobs.retries",
    unit="1",
    description="Number of prediction job retry attempts.",
)
JOB_DURATION = logfire.metric_histogram(
    "sporty.jobs.duration",
    unit="s",
    description="Prediction job execution duration in seconds.",
)
