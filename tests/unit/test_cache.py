"""Unit tests for cache infrastructure."""

import pytest
from unittest.mock import patch, MagicMock

from api.cache import (
    CacheKeys,
    cache_get,
    cache_set,
    cache_delete,
    is_cache_available,
)


class TestCacheKeys:
    """Tests for cache key builders."""

    def test_analysis_key_format(self):
        """Should build analysis key in expected format."""
        key = CacheKeys.analysis_key("circadian", "abc123")
        assert key == "soma:analysis:circadian:abc123"

    def test_baseline_key_format(self):
        """Should build baseline key in expected format."""
        key = CacheKeys.baseline_key("heart_rate")
        assert key == "soma:baseline:heart_rate"

    def test_prefix_consistency(self):
        """All keys should have soma: prefix."""
        assert CacheKeys.ANALYSIS.startswith("soma:")
        assert CacheKeys.BASELINE.startswith("soma:")
        assert CacheKeys.SIGNAL_COUNT.startswith("soma:")


class TestCacheOperations:
    """Tests for cache operations."""

    @patch('api.cache.get_redis')
    def test_cache_get_returns_none_when_redis_unavailable(self, mock_get_redis):
        """Should return None when Redis is not available."""
        mock_get_redis.return_value = None

        result = cache_get("test:key")
        assert result is None

    @patch('api.cache.get_redis')
    def test_cache_get_returns_none_for_missing_key(self, mock_get_redis):
        """Should return None for missing keys."""
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_get_redis.return_value = mock_client

        result = cache_get("test:key")
        assert result is None

    @patch('api.cache.get_redis')
    def test_cache_get_deserializes_json(self, mock_get_redis):
        """Should deserialize JSON values from cache."""
        mock_client = MagicMock()
        mock_client.get.return_value = '{"foo": "bar", "count": 42}'
        mock_get_redis.return_value = mock_client

        result = cache_get("test:key")
        assert result == {"foo": "bar", "count": 42}

    @patch('api.cache.get_redis')
    def test_cache_set_returns_false_when_redis_unavailable(self, mock_get_redis):
        """Should return False when Redis is not available."""
        mock_get_redis.return_value = None

        result = cache_set("test:key", {"data": "value"})
        assert result is False

    @patch('api.cache.get_redis')
    def test_cache_set_serializes_value(self, mock_get_redis):
        """Should serialize values to JSON."""
        mock_client = MagicMock()
        mock_get_redis.return_value = mock_client

        cache_set("test:key", {"data": "value"}, ttl_seconds=3600)

        mock_client.setex.assert_called_once()
        args = mock_client.setex.call_args[0]
        assert args[0] == "test:key"
        assert args[1] == 3600

    @patch('api.cache.get_redis')
    def test_cache_delete_returns_false_when_unavailable(self, mock_get_redis):
        """Should return False when Redis is not available."""
        mock_get_redis.return_value = None

        result = cache_delete("test:key")
        assert result is False

    @patch('api.cache.get_redis')
    def test_cache_delete_calls_redis(self, mock_get_redis):
        """Should call Redis delete."""
        mock_client = MagicMock()
        mock_get_redis.return_value = mock_client

        cache_delete("test:key")

        mock_client.delete.assert_called_once_with("test:key")


class TestCacheAvailability:
    """Tests for cache availability checking."""

    @patch('api.cache.get_redis')
    def test_returns_false_when_client_is_none(self, mock_get_redis):
        """Should return False when no Redis client."""
        mock_get_redis.return_value = None

        assert is_cache_available() is False

    @patch('api.cache.get_redis')
    def test_returns_true_when_ping_succeeds(self, mock_get_redis):
        """Should return True when Redis ping succeeds."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_get_redis.return_value = mock_client

        assert is_cache_available() is True

    @patch('api.cache.get_redis')
    def test_returns_false_when_ping_fails(self, mock_get_redis):
        """Should return False when Redis ping fails."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = Exception("Connection refused")
        mock_get_redis.return_value = mock_client

        assert is_cache_available() is False
