"""Reuse expensive checks only while constructing one synchronous read view.

These scopes must not enclose mutations, commits or provider execution. Ordinary
guards outside a scope always query current state. Each entry owns a fresh cache;
even a nested entry cannot inherit an earlier view's decisions.
"""
from copy import deepcopy
from functools import wraps

_KEY = "research_read_view"


def read_view(function):
    @wraps(function)
    def wrapped(session, *args, **kwargs):
        previous = session.info.get(_KEY)
        session.info[_KEY] = {}
        try:
            return function(session, *args, **kwargs)
        finally:
            if previous is None:
                session.info.pop(_KEY, None)
            else:
                session.info[_KEY] = previous
    return wrapped


def read_once(function):
    @wraps(function)
    def wrapped(session, entity, **kwargs):
        cache = session.info.get(_KEY)
        # An explicitly supplied review context has its own evidence binding.
        if cache is None or any(value is not None for value in kwargs.values()):
            return function(session, entity, **kwargs)
        key = function, entity
        if key not in cache:
            cache[key] = deepcopy(function(session, entity, **kwargs))
        return deepcopy(cache[key])
    return wrapped
