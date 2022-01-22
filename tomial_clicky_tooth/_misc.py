"""Dumping ground for random bits and bobs."""

import numpy as np
import numbers


def copy_name_wrapper(wrapper):

    def wrapped(function):
        wrapped_function = wrapper(function)
        wrapped_function.__name__ = function.__name__
        wrapped_function.__qualname__ = function.__qualname__
        wrapped_function.__doc__ = function.__doc__
        return wrapped_function

    return wrapped


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
