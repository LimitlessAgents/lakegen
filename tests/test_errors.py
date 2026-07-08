"""Tests for lakegen.core.error.base and code."""

import pytest

from lakegen.core.error.base import BaseError
from lakegen.core.error.code import ErrorCode


def test_to_dict_basic():
    err = BaseError(ErrorCode.NOT_FOUND, "not found")
    d = err.to_dict()
    assert d["code"] == "NOT_FOUND"
    assert d["message"] == "not found"
    assert d["cause"] is None
    assert d["details"] is None


def test_to_dict_with_details():
    err = BaseError(ErrorCode.INVALID_ARGUMENT, "bad input", details={"field": "name"})
    d = err.to_dict()
    assert d["details"] == {"field": "name"}


def test_cause_chain_base_error():
    inner = BaseError(ErrorCode.JSON, "corrupt file", is_retryable=True)
    outer = BaseError(ErrorCode.INTERNAL, "wrapper")
    raise_outer = None
    try:
        raise outer from inner
    except BaseError as e:
        raise_outer = e

    d = raise_outer.to_dict()
    assert d["cause"]["code"] == "JSON"
    assert d["cause"]["message"] == "corrupt file"


def test_cause_chain_plain_exception():
    plain = ValueError("raw")
    err = BaseError(ErrorCode.INTERNAL, "wrap")
    try:
        raise err from plain
    except BaseError as e:
        d = e.to_dict()
    assert d["cause"]["type"] == "ValueError"
    assert d["cause"]["message"] == "raw"


def test_retryable_explicit():
    err = BaseError(ErrorCode.CONNECTION_FAILED, "timeout", is_retryable=True)
    assert err.is_retryable is True


def test_retryable_default_false():
    err = BaseError(ErrorCode.INTERNAL, "oops")
    assert err.is_retryable is False


def test_retryable_inherits_from_cause():
    inner = BaseError(ErrorCode.CONNECTION_TIMEOUT, "timeout", is_retryable=True)
    outer = BaseError(ErrorCode.INTERNAL, "wrap")
    try:
        raise outer from inner
    except BaseError as e:
        assert e.is_retryable is True


def test_user_fixable_default_true():
    err = BaseError(ErrorCode.INVALID_ARGUMENT, "bad")
    assert err.is_user_fixable is True


def test_user_fixable_explicit_false():
    err = BaseError(ErrorCode.INTERNAL, "bug", is_user_fixable=False)
    assert err.is_user_fixable is False


def test_str_representation():
    err = BaseError(ErrorCode.NOT_FOUND, "missing thing")
    assert str(err) == "NOT_FOUND: missing thing"


def test_cause_constructor_arg():
    plain = RuntimeError("low-level")
    err = BaseError(ErrorCode.INTERNAL, "wrap", cause=plain)
    d = err.to_dict()
    assert d["cause"]["type"] == "RuntimeError"
