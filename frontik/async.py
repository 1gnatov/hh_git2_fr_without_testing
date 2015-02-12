# -*- coding: utf-8 -*-

import time
import logging

from tornado.ioloop import IOLoop

default_logger = logging.getLogger('frontik.async')


class AsyncGroup(object):
    """
    Grouping of several async requests and final callback in such way that final callback is invoked
    after the last request is finished.

    If any callback throws an exception, all pending callbacks would be aborted and finish_cb
    would not be automatically called.
    """

    def __init__(self, finish_cb, log=default_logger.debug, name=None, logger=None):
        self._counter = 0
        self._finish_cb = finish_cb
        self._finish_cb_called = False
        self._aborted = False
        self._logger = logger if logger is not None else default_logger
        self._name = name

        self._start_time = time.time()

        if self._name is not None:
            self._log_name = '{0} group'.format(self._name)
        else:
            self._log_name = 'group'

    def _message(self, message):
        return self._log_name + ': ' + message

    def abort(self):
        self._logger.info(self._message('aborting async group'))
        self._aborted = True

    def finish(self):
        if not self._finish_cb_called:
            self._logger.debug(self._message('done in %.2fms'), (time.time() - self._start_time) * 1000.)
            self._finish_cb_called = True

            try:
                self._finish_cb()
            finally:
                # prevent possible cycle references
                self._finish_cb = None

    def try_finish(self):
        if self._counter == 0:
            self.finish()

    def try_finish_async(self):
        """Executes finish_cb in next IOLoop iteration"""
        if self._counter == 0:
            IOLoop.instance().add_callback(self.finish)

    def _inc(self):
        assert not self._finish_cb_called
        self._counter += 1

    def _dec(self):
        self._counter -= 1
        self._logger.debug(self._message('%s requests pending'), self._counter)

    def add(self, intermediate_cb):
        self._inc()

        def new_cb(*args, **kwargs):
            if not self._finish_cb_called and not self._aborted:
                try:
                    self._dec()
                    intermediate_cb(*args, **kwargs)
                except Exception:
                    self._logger.error(self._message('aborting async group due to unhandled exception in callback'))
                    self._logger.debug(self._message('done in %.2fms'), (time.time() - self._start_time) * 1000.)
                    self._aborted = True
                    raise

                self.try_finish()
            else:
                self._logger.info(self._message('ignoring response because of already finished group'))

        return new_cb

    def add_notification(self):
        self._inc()

        def new_cb(*args, **kwargs):
            self._dec()
            self.try_finish()

        return new_cb
