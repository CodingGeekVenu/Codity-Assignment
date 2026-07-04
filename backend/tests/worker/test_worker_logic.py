import pytest
from app.worker import calculate_next_retry
from app.models import RetryStrategy

def test_fixed_retry_backoff():
    # attempt 1
    assert calculate_next_retry(1, RetryStrategy.FIXED) == 60
    # attempt 2
    assert calculate_next_retry(2, RetryStrategy.FIXED) == 60
    # attempt 5
    assert calculate_next_retry(5, RetryStrategy.FIXED) == 60

def test_linear_retry_backoff():
    # attempt 1 => 1 * 60 = 60
    assert calculate_next_retry(1, RetryStrategy.LINEAR) == 60
    # attempt 3 => 3 * 60 = 180
    assert calculate_next_retry(3, RetryStrategy.LINEAR) == 180

def test_exponential_retry_backoff():
    # attempt 1 => 2^0 * 60 = 60
    assert calculate_next_retry(1, RetryStrategy.EXPONENTIAL) == 60
    # attempt 2 => 2^1 * 60 = 120
    assert calculate_next_retry(2, RetryStrategy.EXPONENTIAL) == 120
    # attempt 4 => 2^3 * 60 = 480
    assert calculate_next_retry(4, RetryStrategy.EXPONENTIAL) == 480
