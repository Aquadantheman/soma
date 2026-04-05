"""Unit tests for job queue infrastructure."""

import pytest
from unittest.mock import patch, MagicMock

from api.jobs.queue import (
    QueueName,
    JobStatus,
    get_job_status,
    enqueue_job,
)


class TestQueueNames:
    """Tests for queue name constants."""

    def test_queue_names_have_prefix(self):
        """All queue names should have soma: prefix."""
        assert QueueName.DEFAULT.startswith("soma:")
        assert QueueName.HIGH.startswith("soma:")
        assert QueueName.LOW.startswith("soma:")
        assert QueueName.SCHEDULED.startswith("soma:")


class TestJobStatus:
    """Tests for job status enum."""

    def test_job_status_values(self):
        """Should have expected status values."""
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.STARTED == "started"
        assert JobStatus.FINISHED == "finished"
        assert JobStatus.FAILED == "failed"


class TestGetJobStatus:
    """Tests for job status retrieval."""

    @patch('api.jobs.queue.get_connection')
    def test_returns_unavailable_when_no_connection(self, mock_get_conn):
        """Should return unavailable status when no connection."""
        mock_get_conn.return_value = None

        result = get_job_status("test-job-id")

        assert result.job_id == "test-job-id"
        assert result.status == JobStatus.UNAVAILABLE

    @patch('api.jobs.queue.get_connection')
    def test_returns_not_found_for_missing_job(self, mock_get_conn):
        """Should return not_found for non-existent job."""
        mock_get_conn.return_value = MagicMock()

        # The Job.fetch will fail since there's no actual Redis
        result = get_job_status("missing-job-id")

        assert result.status == JobStatus.NOT_FOUND


class TestEnqueueJob:
    """Tests for job enqueueing."""

    @patch('api.jobs.queue.get_queue')
    def test_returns_none_when_queue_unavailable(self, mock_get_queue):
        """Should return None when queue is unavailable."""
        mock_get_queue.return_value = None

        def dummy_task():
            pass

        result = enqueue_job(dummy_task)

        assert result is None

    @patch('api.jobs.queue.get_queue')
    def test_enqueues_job_successfully(self, mock_get_queue):
        """Should enqueue job and return job ID."""
        mock_queue = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "test-job-123"
        mock_queue.enqueue.return_value = mock_job
        mock_get_queue.return_value = mock_queue

        def dummy_task():
            pass

        result = enqueue_job(dummy_task)

        assert result == "test-job-123"
        mock_queue.enqueue.assert_called_once()

    @patch('api.jobs.queue.get_queue')
    def test_passes_timeout_to_queue(self, mock_get_queue):
        """Should pass job_timeout to queue."""
        mock_queue = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "test-job-123"
        mock_queue.enqueue.return_value = mock_job
        mock_get_queue.return_value = mock_queue

        def dummy_task():
            pass

        enqueue_job(dummy_task, job_timeout=1800)

        call_kwargs = mock_queue.enqueue.call_args[1]
        assert call_kwargs["job_timeout"] == 1800

    @patch('api.jobs.queue.get_queue')
    def test_selects_correct_queue(self, mock_get_queue):
        """Should use specified queue name."""
        mock_queue = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "test-job-123"
        mock_queue.enqueue.return_value = mock_job
        mock_get_queue.return_value = mock_queue

        def dummy_task():
            pass

        enqueue_job(dummy_task, queue_name=QueueName.HIGH)

        mock_get_queue.assert_called_with(QueueName.HIGH)
