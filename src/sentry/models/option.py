"""
sentry.models.option
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010-2014 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import, print_function

from builtins import object
from django.db import models
from django.utils import timezone

from sentry.db.models import Model, sane_repr
from sentry.db.models.fields import EncryptedPickledObjectField


class Option(Model):
    """
    Global options which apply in most situations as defaults,
    and generally can be overwritten by per-project options.

    Options which are specific to a plugin should namespace
    their key. e.g. key='myplugin:optname'
    """
    __core__ = True

    key = models.CharField(max_length=64, unique=True)
    value = EncryptedPickledObjectField()
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta(object):
        app_label = 'sentry'
        db_table = 'sentry_option'

    __repr__ = sane_repr('key', 'value')
