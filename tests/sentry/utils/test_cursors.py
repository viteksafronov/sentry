from __future__ import absolute_import

import math

from mock import Mock

from sentry.utils.cursors import build_cursor, Cursor


def build_mock(**attrs):
    obj = Mock()
    for key, value in list(attrs.items()):
        setattr(obj, key, value)
    obj.__repr__ = lambda x: repr(attrs)
    return obj


def test_build_cursor():
    event1 = build_mock(id=1.1, message='one')
    event2 = build_mock(id=1.1, message='two')
    event3 = build_mock(id=2.1, message='three')

    results = [event1, event2, event3]

    def item_key(key, for_prev=False):
        return math.floor(key.id)

    cursor_kwargs = {
        'key': item_key,
        'limit': 1,
    }

    cursor = build_cursor(results, **cursor_kwargs)
    assert isinstance(cursor.__next__, Cursor)
    assert cursor.__next__
    assert isinstance(cursor.prev, Cursor)
    assert not cursor.prev
    assert list(cursor) == [event1]

    cursor = build_cursor(results[1:], cursor=cursor.__next__, **cursor_kwargs)
    assert isinstance(cursor.__next__, Cursor)
    assert cursor.__next__
    assert isinstance(cursor.prev, Cursor)
    assert cursor.prev
    assert list(cursor) == [event2]

    cursor = build_cursor(results[2:], cursor=cursor.__next__, **cursor_kwargs)
    assert isinstance(cursor.__next__, Cursor)
    assert not cursor.__next__
    assert isinstance(cursor.prev, Cursor)
    assert cursor.prev
    assert list(cursor) == [event3]
