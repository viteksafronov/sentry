"""
sentry.services.base
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010-2014 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import, print_function


from builtins import object
class Service(object):
    name = ''

    def __init__(self, debug=False):
        self.debug = debug
