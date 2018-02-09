# -*- coding: utf-8 -*-
import time
import subprocess
import threading


class TimeoutCommand(object):
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None

    def run(self, timeout):
        def target():
            self.process = subprocess.Popen(self.cmd, shell=True)
            self.process.communicate()

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            self.process.terminate()
            thread.join()
            raise TimeoutException


class TimeoutException(Exception):
    pass


def wait_until(func,
               check_return_value=True,
               total_timeout=60,
               interval=0.5,
               exc_list=None,
               error_message="",
               *args,
               **kwargs):
    """
    Waits until func(*args, **kwargs),
    until total_timeout seconds,
    for interval seconds interval,
    while catching exceptions given in exc_list.
    If it ends in time, it re-returns the return value from the called function.
    """
    start_function = time.time()
    while time.time() - start_function < total_timeout:

        try:
            return_value = func(*args, **kwargs)
            if not check_return_value or (check_return_value and return_value):
                return return_value

        except Exception as e:
            if exc_list and any([isinstance(e, x) for x in exc_list]):
                pass
            else:
                raise

        time.sleep(interval)

    raise TimeoutException(error_message)


def wait_until_no_timeout_exception(func,
                                    total_timeout=60,
                                    interval=0.5,
                                    exc_list=None,
                                    *args,
                                    **kwargs):
    try:
        return wait_until(func,
                          check_return_value=False,
                          total_timeout=total_timeout,
                          interval=interval,
                          exc_list=exc_list,
                          *args,
                          **kwargs)
    except TimeoutException:
        return func(**kwargs)
