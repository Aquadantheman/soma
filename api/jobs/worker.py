"""RQ Worker configuration for Soma background jobs.

Run with:
    python -m api.jobs.worker

Or using rq directly:
    rq worker soma:high soma:default soma:low --url redis://localhost:6379/0
"""

import os
import sys


def main():
    """Start the RQ worker."""
    try:
        from rq import Worker, Connection
        import redis
    except ImportError:
        print("Error: rq and redis packages are required.")
        print("Install with: pip install rq redis")
        sys.exit(1)

    from .queue import QueueName, get_connection

    # Get Redis connection
    redis_url = os.getenv("SOMA_REDIS_URL", "redis://localhost:6379/0")
    conn = redis.from_url(redis_url)

    # Test connection
    try:
        conn.ping()
        print(f"Connected to Redis at {redis_url}")
    except redis.ConnectionError:
        print(f"Error: Cannot connect to Redis at {redis_url}")
        sys.exit(1)

    # Queue priority order (high to low)
    queues = [
        QueueName.HIGH,
        QueueName.DEFAULT,
        QueueName.LOW,
        QueueName.SCHEDULED,
    ]

    print(f"Starting worker for queues: {', '.join(queues)}")
    print("Press Ctrl+C to stop")

    with Connection(conn):
        worker = Worker(queues)
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
