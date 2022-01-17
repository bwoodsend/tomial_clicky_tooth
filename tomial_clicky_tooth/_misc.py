"""Dumping ground for random bits and bobs."""

import numpy as np
import types
import operator
import numbers


def set_to_array(s, dtype=float):
    return np.fromiter(iter(s), count=len(s), dtype=dtype)


def sep_last_ax(points):
    points = np.asarray(points)
    return tuple(points[..., i] for i in range(points.shape[-1]))


def rms(x, axis=None):
    return np.sqrt(np.mean(np.asarray(x)**2, axis))


def set_element_0(s):
    for i in s:
        return i


def arg_array_inv(args, out_len=None, default=None):
    out_len = out_len or len(args)
    out = np.empty(out_len, args.dtype)
    if default is not None:
        out.fill(default)

    out[args] = np.arange(len(args))
    return out


def random_selection(lst, size=None):
    indices = np.random.randint(0, len(lst), size)

    return np.asarray(lst)[indices]


def as_str(x):
    if isinstance(x, str):
        return x
    elif isinstance(x, bytes):
        return x.decode(errors="replace")
    else:
        return str(x)


def copy_name_wrapper(wrapper):

    def wrapped(function):
        wrapped_function = wrapper(function)
        wrapped_function.__name__ = function.__name__
        wrapped_function.__qualname__ = function.__qualname__
        wrapped_function.__doc__ = function.__doc__
        return wrapped_function

    return wrapped


class _LazyAttribute(property):
    pass


def LazyAttribute(func):
    """

    :rtype: property
    """
    attr = func.__name__
    priv_attr = "_" + attr

    def getter(self):
        if not hasattr(self, priv_attr):
            setattr(self, priv_attr, func(self))
        return getattr(self, priv_attr)

    def deleter(self):
        if hasattr(self, priv_attr):
            delattr(self, priv_attr)

    return _LazyAttribute(getter, None, deleter, func.__doc__)


def cached(cache_getter):
    if isinstance(cache_getter, str):
        cache_getter = operator.attrgetter(cache_getter)

    @copy_name_wrapper
    def wrapper(function):

        def wrapped(self, *key):
            cache = cache_getter(self)
            if key in cache:
                return cache[key]
            out = function(self, *key)
            cache[key] = out
            return out

        return wrapped

    return wrapper


# noinspection PyUnboundLocalVariable
def all_equal(x):
    x = iter(x)
    for first in x:
        break
    for i in x:
        if np.any(i != first):
            return False
    return True


def fussy_zip(*iters):
    assert all_equal([len(i) for i in iters])
    return zip(*iters)


@copy_name_wrapper
def accept_generators(function):

    def wrapped(*args, **kwargs):
        if len(args) == 1 and isinstance(args[0], types.GeneratorType):
            return function(*args[0], **kwargs)
        return function(*args, **kwargs)

    return wrapped


def choose_int_type(min, max=None):
    if max is None:
        max = min
    assert min <= max
    signed = min < 0
    for i in [8, 16, 32, 64]:
        limit = 1 << i
        if signed:
            limit /= 2
        if -limit <= min <= max < limit:
            return getattr(np, "{}int{}".format(["u", ""][signed], i))
    raise ValueError("Could not find a suitable int type for ({}, {})".format(
        min, max))


def astype(arr, dtype):
    return np.frombuffer(arr.tobytes(), dtype)


@accept_generators
def mask_or(mask, *masks):
    for m in masks:
        mask = mask | m
    return mask


@accept_generators
def mask_and(mask, *masks):
    for m in masks:
        mask = mask & m
    return mask


@accept_generators
def mask_and_accumulative(mask, *masks):
    out = mask.copy()
    for m in masks:
        out[out] &= m
    return out


def remap_ids(mask, shape=None, fill_value=None, dtype=int):
    if isinstance(mask, tuple):
        mask = mask[0]
    if mask.dtype == bool:
        enum = np.arange(mask.sum())
        shape = mask.shape
    else:
        assert shape is not None
        enum = np.arange(len(mask))

    remap = np.empty(shape, dtype)
    if fill_value is not None:
        remap.fill(fill_value)
    remap[mask] = enum

    return remap


@copy_name_wrapper
def multiitemsable(singular):
    """Decorates a ``__getitem__()`` or ``__setitem__()`` method so that it
    handles lists or arrays of indices implicitly similarly to indexing a
    numpy array."""

    def __x_item__(self, index, *value):
        if isinstance(index, numbers.Integral):
            return singular(self, index, *value)
        if isinstance(index, list):
            return [singular(self, index, *value) for index in index]
        if isinstance(index, np.ndarray):
            if value:
                value = (np.asarray(value[0]).flat,)
            values = np.array(
                [singular(self, *args) for args in zip(index.flat, *value)])
            values = values.reshape(index.shape + (-1,))
            if values.shape[-1] == 1:
                values = values[..., 0]
            return values
        return singular(self, index, *value)

    return __x_item__


@copy_name_wrapper
def sliceable(singular):
    """Decorates a ``__getitem__()`` or ``__setitem__()`` method so that it
    handles slices implicitly. The ``__len__()`` function must be defined. Output
    is always a list."""

    def __x_item__(self, index, *value):
        if isinstance(index, slice):
            return [
                singular(self, *args)
                for args in zip(range(*index.indices(len(self))), *value)
            ]
        return singular(self, index, *value)

    return __x_item__


if __name__ == "__main__":
    pass
