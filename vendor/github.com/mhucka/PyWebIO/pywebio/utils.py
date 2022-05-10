import asyncio
import functools
import inspect
import os
import queue
import random
import socket
import string
import time
from collections import OrderedDict
from contextlib import closing
from os.path import abspath, dirname

project_dir = dirname(abspath(__file__))

STATIC_PATH = '%s/html' % project_dir


class Setter:
    """
    可以在对象属性上保存数据。
    访问数据对象不存在的属性时会返回None而不是抛出异常。
    """

    def __getattribute__(self, name):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return None


class ObjectDictProxy:
    """
    通过属性访问的字典。实例不维护底层字典，而是每次在访问时使用回调函数获取

    在对象属性上保存的数据会被保存到底层字典中
    访问数据对象不存在的属性时会返回None而不是抛出异常。
    不能保存下划线开始的属性
    用 ``obj._dict`` 获取对象的字典表示

    Example::

        d = {}
        data = LazyObjectDict(lambda: d)

        data.name = "Wang"
        data.age = 22
        assert data.foo is None
        data[10] = "10"

        for key in data:
            print(key)

        assert 'bar' not in data
        assert 'name' in data

        assert data._dict is d
        print(data._dict)
    """

    def __init__(self, dict_getter):
        # 使用 self.__dict__ 避免触发 __setattr__
        self.__dict__['_dict_getter'] = dict_getter

    @property
    def _dict(self):
        return self._dict_getter()

    def __len__(self):
        return len(self._dict)

    def __getitem__(self, key):
        if key in self._dict:
            return self._dict[key]
        raise KeyError(key)

    def __setitem__(self, key, item):
        self._dict[key] = item

    def __delitem__(self, key):
        del self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __contains__(self, key):
        return key in self._dict

    def __repr__(self):
        return repr(self._dict)

    def __setattr__(self, key, value):
        """
        无论属性是否存在都会被调用
        使用 self.__dict__[name] = value  避免递归
        """
        assert not key.startswith('_'), "Cannot set attributes starting with underscore"
        self._dict.__setitem__(key, value)

    def __getattr__(self, item):
        """访问一个不存在的属性时触发"""
        return self._dict.get(item, None)

    def __delattr__(self, item):
        try:
            del self._dict[item]
        except KeyError:
            pass


class ObjectDict(dict):
    """
    Object like dict, every dict[key] can visite by dict.key

    If dict[key] is `Get`, calculate it's value.
    """

    def __getattr__(self, name):
        ret = self.__getitem__(name)
        if hasattr(ret, '__get__'):
            return ret.__get__(self, ObjectDict)
        return ret


def catch_exp_call(func, logger):
    """运行函数，将捕获异常记录到日志

    :param func: 函数
    :param logger: 日志
    :return: ``func`` 返回值
    """
    try:
        return func()
    except Exception:
        logger.exception("Error when invoke `%s`" % func)


def iscoroutinefunction(object):
    while isinstance(object, functools.partial):
        object = object.func
    return asyncio.iscoroutinefunction(object)


def isgeneratorfunction(object):
    while isinstance(object, functools.partial):
        object = object.func
    return inspect.isgeneratorfunction(object)


def get_function_name(func, default=None):
    while isinstance(func, functools.partial):
        func = func.func
    return getattr(func, '__name__', default)


def get_function_doc(func):
    """获取函数的doc注释

    如果函数被functools.partial包装，则返回内部原始函数的文档，可以通过设置新函数的 func.__doc__ 属性来更新doc注释
    """
    partial_doc = inspect.getdoc(functools.partial)
    if isinstance(func, functools.partial) and getattr(func, '__doc__', '') == partial_doc:
        while isinstance(func, functools.partial):
            func = func.func
    return inspect.getdoc(func) or ''


def get_function_seo_info(func):
    """获取使用 pywebio.platform.utils.seo() 设置在函数上的SEO信息
    """
    if hasattr(func, '_pywebio_title'):
        return func._pywebio_title, func._pywebio_description

    while isinstance(func, functools.partial):
        func = func.func
        if hasattr(func, '_pywebio_title'):
            return func._pywebio_title, func._pywebio_description

    return None


class LimitedSizeQueue(queue.Queue):
    """
    有限大小的队列

    `get()` 返回全部数据
    队列满时，再 `put()` 会阻塞
    """

    def get(self):
        """获取队列全部数据"""
        try:
            return super().get(block=False)
        except queue.Empty:
            return []

    def wait_empty(self, timeout=None):
        """等待队列内的数据被取走"""
        with self.not_full:
            if self._qsize() == 0:
                return

            if timeout is None:
                self.not_full.wait()
            elif timeout < 0:
                raise ValueError("'timeout' must be a non-negative number")
            else:
                self.not_full.wait(timeout)

    def _init(self, maxsize):
        self.queue = []

    def _qsize(self):
        return len(self.queue)

    # Put a new item in the queue
    def _put(self, item):
        self.queue.append(item)

    # Get an item from the queue
    def _get(self):
        all_data = self.queue
        self.queue = []
        return all_data


async def wait_host_port(host, port, duration=10, delay=2):
    """Repeatedly try if a port on a host is open until duration seconds passed

    from: https://gist.github.com/betrcode/0248f0fda894013382d7#gistcomment-3161499

    :param str host: host ip address or hostname
    :param int port: port number
    :param int/float duration: Optional. Total duration in seconds to wait, by default 10
    :param int/float delay: Optional. Delay in seconds between each try, by default 2
    :return: awaitable bool
    """
    tmax = time.time() + duration
    while time.time() < tmax:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
            writer.close()

            # asyncio.StreamWriter.wait_closed is introduced in py 3.7
            # See https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.wait_closed
            if hasattr(writer, 'wait_closed'):
                await writer.wait_closed()

            return True
        except Exception:
            if delay:
                await asyncio.sleep(delay)
    return False


def get_free_port():
    """
    pick a free port number
    :return int: port number
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def random_str(length=16):
    """生成字母和数组组成的随机字符串

    :param int length: 字符串长度
    """
    candidates = string.ascii_letters + string.digits
    return ''.join(random.SystemRandom().choice(candidates) for _ in range(length))


def run_as_function(gen):
    res = None
    while 1:
        try:
            res = gen.send(res)
        except StopIteration as e:
            if len(e.args) == 1:
                return e.args[0]
            return


async def to_coroutine(gen):
    res = None
    while 1:
        try:
            c = gen.send(res)
            res = await c
        except StopIteration as e:
            if len(e.args) == 1:
                return e.args[0]
            return


class LRUDict(OrderedDict):
    """
    Store items in the order the keys were last recent updated.

    The last recent updated item was in end.
    The last furthest updated item was in front.
    """

    def __setitem__(self, key, value):
        OrderedDict.__setitem__(self, key, value)
        self.move_to_end(key)


_html_value_chars = set(string.ascii_letters + string.digits + '_-')


def is_html_safe_value(val):
    """检查是字符串是否可以作为html属性值"""
    return all(i in _html_value_chars for i in val)


def check_webio_js():
    js_files = [os.path.join(STATIC_PATH, 'js', i) for i in ('pywebio.js', 'pywebio.min.js')]
    if any(os.path.isfile(f) for f in js_files):
        return
    error_msg = """
Error: Missing pywebio.js library for frontend page.
This may be because you cloned or downloaded the project directly from the Git repository.

You Can:
  * Manually build the pywebio.js file. See `webiojs/README.md` for more info.
OR
  * Use the following command to install the latest development version of PyWebIO:
    pip3 install -U https://code.aliyun.com/wang0618/pywebio/repository/archive.zip
""".strip()
    raise RuntimeError(error_msg)
