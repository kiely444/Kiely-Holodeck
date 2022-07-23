"""Utility functions and tools.

References
----------
* [Peters1964]_ Peters 1964
* [Enoki2004]_ Enoki, Inoue, Nagashima, & Sugiyama 2004
* [Sesana2004]_ Sesana, Haardt, Madau, & Volonteri 2004
* [EN07]_ Enoki & Nagashima 2007

"""

import abc
import copy
import numbers
import os
from typing import Optional, Tuple, Union, List  # , Sequence,

import numpy as np
import numpy.typing as npt
import scipy as sp
import scipy.stats
import h5py

from holodeck import log
from holodeck.constants import NWTG, SCHW, SPLC, YR

# e.g. [Sesana2004]_ Eq.36
_GW_SRC_CONST = 8 * np.power(NWTG, 5/3) * np.power(np.pi, 2/3) / np.sqrt(10) / np.power(SPLC, 4)
_GW_DADT_SEP_CONST = - 64 * np.power(NWTG, 3) / 5 / np.power(SPLC, 5)
_GW_DEDT_ECC_CONST = - 304 * np.power(NWTG, 3) / 15 / np.power(SPLC, 5)
# [EN07]_, Eq.2.2
_GW_LUM_CONST = (32.0 / 5.0) * np.power(NWTG, 7.0/3.0) * np.power(SPLC, -5.0)


class _Modifier(abc.ABC):
    """Base class for all types of post-processing modifiers.

    Notes
    -----
    * Must be subclassed for use.
    * ``__call__(base)`` ==> ``modify(base)``

    """

    def __call__(self, base):
        self.modify(base)
        return

    @abc.abstractmethod
    def modify(self, base):
        pass


# =================================================================================================
# ====    General Logistical    ====
# =================================================================================================


def load_hdf5(fname, keys=None):
    """Load data and header information from HDF5 files into dictionaries.

    Parameters
    ----------
    fname : str
        Filename to load (must be an `hdf5` file).
    keys : None or (list of str)
        Specific keys to load from the top-level of the HDF5 file.
        `None`: load all top-level keys.

    Returns
    -------
    header : dict,
        All entries from `hdf5.File.attrs`, typically used for meta-data.
    data : dict,
        All top level datasets from the hdf5 file,
        specifically everything returned from `hdf5.File.keys()`.

    """
    squeeze = False
    if (keys is not None) and np.isscalar(keys):
        keys = [keys]
        squeeze = True

    header = dict()
    data = dict()
    with h5py.File(fname, 'r') as h5:
        head_keys = h5.attrs.keys()
        for kk in head_keys:
            header[kk] = copy.copy(h5.attrs[kk])

        if keys is None:
            keys = h5.keys()

        for kk in keys:
            data[kk] = h5[kk][:]

    if squeeze:
        data = data[kk]

    return header, data


def python_environment():
    """Tries to determine the current python environment, one of: 'jupyter', 'ipython', 'terminal'.

    Returns
    -------
    str
        Description of the current python environment, one of ['jupter', 'ipython', 'terminal'].

    """
    try:
        # NOTE: `get_ipython` should *not* be explicitly imported from anything
        #       it will be defined if this is called from a jupyter or ipython environment
        ipy_str = str(type(get_ipython())).lower()  # noqa
        if 'zmqshell' in ipy_str:
            return 'jupyter'
        if 'terminal' in ipy_str:
            return 'ipython'
    except:
        return 'terminal'

    raise RuntimeError(f"unexpected result from `get_ipython()`: '{ipy_str}'!")


def tqdm(*args, **kwargs):
    """Construct a progress bar appropriately based on the current environment (script vs. notebook)

    Parameters
    ----------
    *args, **kwargs : All arguments are passed directory to the `tqdm` constructor.

    Returns
    -------
    `tqdm.tqdm_gui`
        Decorated iterator that shows a progress bar.

    """
    if python_environment().lower().startswith('jupyter'):
        import tqdm.notebook
        tqdm_method = tqdm.notebook.tqdm
    else:
        import tqdm
        tqdm_method = tqdm.tqdm

    return tqdm_method(*args, **kwargs)


def get_file_size(fnames, precision=1):
    """Return a human-readable size of a file or set of files.

    Parameters
    ----------
    fnames : str or list
        Paths to target file(s)
    precisions : int,
        Sesired decimal precision of output

    Returns
    -------
    byte_str : str
        Human-readable size of file(s)

    """
    fnames = np.atleast_1d(fnames)

    byte_size = 0.0
    for fil in fnames:
        byte_size += os.path.getsize(fil)

    abbrevs = (
        (1 << 50, 'PiB'),
        (1 << 40, 'TiB'),
        (1 << 30, 'GiB'),
        (1 << 20, 'MiB'),
        (1 << 10, 'KiB'),
        (1, 'bytes')
    )

    for factor, suffix in abbrevs:
        if byte_size >= factor:
            break

    size = byte_size / factor
    byte_str = f"{size:.{precision:}f} {suffix}"
    return byte_str


def _get_subclass_instance(value, default, superclass):
    """Convert the given `value` into a subclass instance.

    `None` ==> instance from `default` class
    Class ==> instance from that class
    instance ==> check that this is an instance of a subclass of `superclass`, error if not

    Parameters
    ----------
    value : object,
        Object to convert into a class instance.
    default : class,
        Default class constructor to use if `value` is None.
    superclass : class,
        Super/parent class to compare against the class instance from `value` or `default`.
        If the class instance is not a subclass of `superclass`, a ValueError is raised.

    Returns
    -------
    value : object,
        Class instance that is a subclass of `superclass`.

    Raises
    ------
    ValueError : if the class instance is not a subclass of `superclass`.

    """
    import inspect

    # Set `value` to `default` if it is `None`
    if value is None:
        value = default

    # If `value` is a class (constructor), then construct an instance from it
    if inspect.isclass(value):
        value = value()

    # Raise an error if `value` is not a subclass of `superclass`
    if not isinstance(value, superclass):
        err = f"argument ({value}) must be an instance or subclass of `{superclass}`!"
        log.error(err)
        raise ValueError(err)

    return value


# =================================================================================================
# ====    Mathematical & Numerical    ====
# =================================================================================================


def eccen_func(norm: float, std: float, size: int) -> np.ndarray:
    """Draw random values between [0.0, 1.0] with a given center and width.

    This function is a bit contrived, but the `norm` defines the center-point of the distribution,
    and the `std` parameter determines the width of the distribution.  In all cases the resulting
    values are only between [0.0, 1.0].  This function is typically used to draw initial random
    eccentricities.

    Parameters
    ----------
    norm : float,
        Specification of the center-point of the distribution.
    std : float,
        Specification of the width of the distribution.
    size : int,
        Number of samples to draw.

    Returns
    -------
    eccen : ndarray,
        Values between [0.0, 1.0] with shape given by the `size` parameter.

    """
    eccen = log_normal_base_10(1.0/norm, std, size=size)
    eccen = 1.0 / (eccen + 1.0)
    return eccen


def frac_str(vals: npt.ArrayLike, prec: int = 2) -> str:
    """Return a string with the fraction and decimal of non-zero elements of the given array.

    e.g. [0, 1, 2, 0, 0] ==> "2/5 = 4.0e-1"

    Parameters
    ----------
    vals : (N,) array_like,
        Input array to find non-zero elements of.
    prec : int
        Decimal precision in scientific notation string.

    Returns
    -------
    rv : str,
        Fraction string.

    """
    num = np.count_nonzero(vals)
    den = vals.size
    frc = num / den
    rv = f"{num:.{prec}e}/{den:.{prec}e} = {frc:.{prec}e}"
    return rv


def interp(
    xnew: npt.ArrayLike, xold: npt.ArrayLike, yold: npt.ArrayLike,
    left: float = np.nan, right: float = np.nan, xlog: bool = True, ylog: bool = True,
) -> npt.ArrayLike:
    """Linear interpolation of the given arguments in log/lin-log/lin space.

    Parameters
    ----------
    xnew : npt.ArrayLike
        New locations (independent variable) to interpolate to.
    xold : npt.ArrayLike
        Old locations of independent variable.
    yold : npt.ArrayLike
        Old locations of dependent variable.
    left : float, optional
        Fill value for locations below the domain `xold`.
    right : float, optional
        Fill value for locations above the domain `xold`.
    xlog : bool, optional
        Linear interpolation in the log of x values.
    ylog : bool, optional
        Linear interpolation in the log of y values.

    Returns
    -------
    y1 : npt.ArrayLike
        Interpolated output values of the dependent variable.

    """
    x1 = np.asarray(xnew)
    x0 = np.asarray(xold)
    y0 = np.asarray(yold)
    if xlog:
        x1 = np.log10(x1)
        x0 = np.log10(x0)
    if ylog:
        y0 = np.log10(y0)
        if (left is not None) and np.isfinite(left):
            left = np.log10(left)
        if (right is not None) and np.isfinite(right):
            right = np.log10(right)

    y1 = np.interp(x1, x0, y0, left=left, right=right)
    if ylog:
        y1 = np.power(10.0, y1)

    return y1


def isnumeric(val: object) -> bool:
    """Test if the input value can successfully be cast to a float.

    Parameters
    ----------
    val : object
        Value to test.

    Returns
    -------
    bool
        True if the input value can be cast to a float.

    """
    try:
        float(str(val))   # ! FIX: Why does this need to cast to `str` first?
    except ValueError:
        return False

    return True


def isinteger(val: object) -> bool:
    """Test if the input value is an integral (integer) number.

    Parameters
    ----------
    val : object
        Value to test.

    Returns
    -------
    bool
        True if the input value is an integer number.

    """
    rv = isnumeric(val) and isinstance(val, numbers.Integral)
    return rv


def log_normal_base_10(
    mu: float, sigma: float, size: Union[int, List[int]] = None, shift: float = 0.0,
) -> npt.ArrayLike:
    """Draw from a log-normal distribution using base-10 standard-deviation.

    i.e. the `sigma` argument is in "dex", or powers of ten.

    Parameters
    ----------
    mu : float
        Mean value of the distribution.
    sigma : float
        Standard deviation in dex (i.e. powers of ten).
        `sigma=1.0` means a standard deviation of one order of magnitude around mu.
    size : Union[int, list[int]], optional
        Number of values to draw.  Either a single integer, or a tuple of integers describing a shape.
    shift : float, optional

    Returns
    -------
    dist : npt.ArrayLike
        Resulting distribution values.

    """
    _sigma = np.log(10.0 ** sigma)
    dist = np.random.lognormal(np.log(mu) + shift*np.log(10.0), _sigma, size)
    return dist


def minmax(vals: npt.ArrayLike, filter: bool = False) -> np.ndarray:
    """Find the minimum and maximum values in the given array.

    Parameters
    ----------
    vals : npt.ArrayLike
        Input values in which to find extrema.
    filter : bool, optional
        Select only finite values from the input array.

    Returns
    -------
    extr : (2,) np.ndarray
        Minimum and maximum values.

    """
    if filter:
        vv = vals[np.isfinite(vals)]
    else:
        vv = vals
    extr = np.array([np.min(vv), np.max(vv)])
    return extr


def print_stats(stack=True, print_func=print, **kwargs):
    """Print out basic properties and statistics on the input key-value array_like values.

    Parameters
    ----------
    stack : bool,
        Whether or not to print a backtrace to stdout.
    print_func : callable,
        Function to use for returning/printing output.
    kwargs : dict,
        Key-value pairs where values are array_like for the shape/stats to be printed.

    """
    if stack:
        import traceback
        traceback.print_stack()
    for kk, vv in kwargs.items():
        print_func(f"{kk} = shape: {np.shape(vv)}, stats: {stats(vv)}")
    return


def nyquist_freqs(
    dur: float = 15.0*YR, cad: float = 0.1*YR, trim: Optional[Tuple[float, float]] = None
) -> np.ndarray:
    """Calculate Nyquist frequencies for the given timing parameters.

    Parameters
    ----------
    dur : float,
        Duration of observations
    cad : float,
        Cadence of observations
    trim : (2,) or None,
        Specification of minimum and maximum frequencies outside of which to remove values.
        `None` can be used in place of either boundary, e.g. [0.1, None] would mean removing
        frequencies below `0.1` (and not trimming values above a certain limit).

    Returns
    -------
    freqs : ndarray,
        Nyquist frequencies

    """
    fmin = 1.0 / dur
    fmax = 1.0 / cad
    # df = fmin / sample
    df = fmin
    freqs = np.arange(fmin, fmax + df/10.0, df)
    if trim is not None:
        if np.shape(trim) != (2,):
            raise ValueError("`trim` (shape: {}) must be (2,) of float!".format(np.shape(trim)))
        if trim[0] is not None:
            freqs = freqs[freqs > trim[0]]
        if trim[1] is not None:
            freqs = freqs[freqs < trim[1]]

    return freqs


def quantiles(
    values: npt.ArrayLike,
    percs: Optional[npt.ArrayLike] = None,
    sigmas: Optional[npt.ArrayLike] = None,
    weights: Optional[npt.ArrayLike] = None,
    axis: Optional[int] = None,
    values_sorted: bool = False,
) -> np.ndarray:
    """Compute weighted percentiles.

    NOTE: if `values` is a masked array, then only unmasked values are used!

    Parameters
    ----------
    values: (N,)
        input data
    percs: (M,) scalar
        Desired quantiles of the data.  Within range of [0.0, 1.0].
    weights: (N,) or `None`
        Weights for each input data point in `values`.
    axis: int or `None`,
        Axis over which to calculate quantiles.
    values_sorted: bool
        If True, then input values are assumed to already be sorted.
        Otherwise they are sorted before calculating quantiles (for efficiency).

    Returns
    -------
    percs : (M,) float
        Array of quantiles of the input data.

    """
    if not isinstance(values, np.ma.MaskedArray):
        values = np.asarray(values)

    if (percs is None) == (sigmas is None):
        err = "either `percs` or `sigmas`, and not both, must be given!"
        log.error(err)
        raise ValueError(err)

    if percs is None:
        percs = sp.stats.norm.cdf(sigmas)

    if np.ndim(values) > 1:
        if axis is None:
            values = values.flatten()
    elif (axis is not None):
        raise ValueError("Cannot act along axis '{}' for 1D data!".format(axis))

    percs = np.array(percs)
    if weights is None:
        weights = np.ones_like(values)
    weights = np.array(weights)
    try:
        weights = np.ma.masked_array(weights, mask=values.mask)
    except AttributeError:
        pass

    assert np.all(percs >= 0.0) and np.all(percs <= 1.0), 'percentiles should be in [0, 1]'

    if not values_sorted:
        sorter = np.argsort(values, axis=axis)
        values = np.take_along_axis(values, sorter, axis=axis)
        weights = np.take_along_axis(weights, sorter, axis=axis)

    if axis is None:
        weighted_quantiles = np.cumsum(weights) - 0.5 * weights
        weighted_quantiles /= np.sum(weights)
        percs = np.interp(percs, weighted_quantiles, values)
        return percs

    weights = np.moveaxis(weights, axis, -1)
    values = np.moveaxis(values, axis, -1)

    weighted_quantiles = np.cumsum(weights, axis=-1) - 0.5 * weights
    weighted_quantiles /= np.sum(weights, axis=-1)[..., np.newaxis]
    percs = [np.interp(percs, weighted_quantiles[idx], values[idx])
             for idx in np.ndindex(values.shape[:-1])]
    percs = np.array(percs)
    return percs


def stats(vals: npt.ArrayLike, percs: Optional[npt.ArrayLike] = None, prec: int = 2) -> str:
    """Return a string giving quantiles of the given input data.

    Parameters
    ----------
    vals : npt.ArrayLike,
        Input values to get quantiles of.
    percs : npt.ArrayLike, optional
        Quantiles to calculate.
    prec : int, optional
        Precision in scientific notation of output.

    Returns
    -------
    rv : str
        Quantiles of input formatted as a string of scientific notation values.

    Raises
    ------
    TypeError: raised if input data is not iterable.

    """
    try:
        if len(vals) == 0:
            raise TypeError
    except TypeError:
        raise TypeError(f"`vals` (shape={np.shape(vals)}) is not iterable!")

    if percs is None:
        percs = [sp.stats.norm.cdf(1), 0.95, 1.0]
        percs = np.array(percs)
        percs = np.concatenate([1-percs[::-1], [0.5], percs])

    # stats = np.percentile(vals, percs*100)
    stats = quantiles(vals, percs)
    rv = ["{val:.{prec}e}".format(prec=prec, val=ss) for ss in stats]
    rv = ", ".join(rv)
    return rv


def trapz_loglog(
        yy: npt.ArrayLike,
        xx: npt.ArrayLike,
        bounds: Optional[Tuple[float, float]] = None,
        axis: int = -1,
        dlogx: Optional[float] = None,
        lntol: float = 1e-2,
        cumsum: bool = True,
) -> npt.ArrayLike:
    """Calculate integral, given `y = dA/dx` or `y = dA/dlogx` w/ trapezoid rule in log-log space.

    We are calculating the integral `A` given sets of values for `y` and `x`.
    To associate `yy` with `dA/dx` then `dlogx = None` [default], otherwise,
    to associate `yy` with `dA/dlogx` then `dlogx = True` for natural-logarithm, or `dlogx = b`
    for a logarithm of base `b`.

    For each interval (x[i+1], x[i]), calculate the integral assuming that y is of the form,
        `y = a * x^gamma`

    Parameters
    ----------
    yy : ndarray
    xx : (X,) array_like of scalar,
    bounds : (2,) array_like of scalar,
    axis : int,
    dlogx : scalar or None,
    lntol : scalar,

    Returns
    -------
    integ

    Notes
    -----
    *   When bounds are given that are not identical to input `xx` values, then interpolation must
        be performed.  This can be done on the resulting cumsum'd values, or on the input integrand
        values.  The cumsum values are *not necessarily a power-law* (for negative indices), and thus
        the interpolation is better performed on the input `yy` values.
    *   Interpolating the cumulative-integral works very badly, instead interpolate the x/y values
        initially to obtain the integral at the appropriate locations.

    """
    yy = np.asarray(yy)
    xx = np.asarray(xx)

    if bounds is not None:
        xextr = [xx.min(), xx.max()]
        if (len(bounds) != 2) or (bounds[0] < xextr[0]) or (xextr[1] < bounds[1]):
            err = f"Invalid `bounds` '{bounds}', xx extrema = '{xextr}'!"
            log.error(err)
            raise ValueError(err)

        newy = sp.interpolate.PchipInterpolator(np.log10(xx), np.log10(yy), extrapolate=False)
        newy = newy(bounds)

        ii = np.searchsorted(xx, bounds)
        xx = np.insert(xx, ii, bounds, axis=axis)
        yy = np.insert(yy, ii, newy, axis=axis)
        ii = np.array([ii[0], ii[1]+1])
        assert np.alltrue(xx[ii] == bounds), "FAILED!"

    if np.ndim(yy) != np.ndim(xx):
        if np.ndim(xx) != 1:
            raise ValueError("BAD SHAPES")
        # convert `xx` from shape (N,) to (1, ... N, ..., 1) where all
        # dimensions besides `axis` have length one
        cut = [np.newaxis for ii in range(np.ndim(yy))]
        cut[axis] = slice(None)
        xx = xx[tuple(cut)]

    log_base = np.e
    if dlogx is not None:
        # If `dlogx` is True, then we're using log-base-e (i.e. natural-log)
        # Otherwise, set the log-base to the given value
        if dlogx is not True:
            log_base = dlogx

    # Numerically calculate the local power-law index
    delta_logx = np.diff(np.log(xx), axis=axis)
    gamma = np.diff(np.log(yy), axis=axis) / delta_logx
    xx = np.moveaxis(xx, axis, 0)
    yy = np.moveaxis(yy, axis, 0)
    aa = np.mean([xx[:-1] * yy[:-1], xx[1:] * yy[1:]], axis=0)
    aa = np.moveaxis(aa, 0, axis)
    xx = np.moveaxis(xx, 0, axis)
    yy = np.moveaxis(yy, 0, axis)
    # Integrate dA/dx   ::   A = (x1*y1 - x0*y0) / (gamma + 1)
    if ((dlogx is None) or (dlogx is False)):
        dz = np.diff(yy * xx, axis=axis)
        trapz = dz / (gamma + 1)
        # when the power-law is (near) '-1' then, `A = a * log(x1/x0)`
        idx = np.isclose(gamma, -1.0, atol=lntol, rtol=lntol)

    # Integrate dA/dlogx    ::    A = (y1 - y0) / gamma
    else:
        dy = np.diff(yy, axis=axis)
        trapz = dy / gamma
        # when the power-law is (near) '-1' then, `A = a * log(x1/x0)`
        idx = np.isclose(gamma, 0.0, atol=lntol, rtol=lntol)

    if np.any(idx):
        # if `xx.shape != yy.shape` then `delta_logx` should be shaped (N-1, 1, 1, 1...)
        # broadcast `delta_logx` to the same shape as `idx` in this case
        if np.shape(xx) != np.shape(yy):
            delta_logx = delta_logx * np.ones_like(aa)
        trapz[idx] = aa[idx] * delta_logx[idx]

    integ = trapz / np.log(log_base)
    if cumsum:
        integ = np.cumsum(integ, axis=axis)
    if bounds is not None:
        if not cumsum:
            log.warning("WARNING: bounds is not None, but cumsum is False!")
        integ = np.moveaxis(integ, axis, 0)
        lo, hi = integ[ii-1, ...]
        integ = hi - lo

    return integ


def trapz(yy: npt.ArrayLike, xx: npt.ArrayLike, axis: int = -1, cumsum: bool = True):
    """Perform a cumulative integration along the given axis.

    Parameters
    ----------
    yy : ArrayLike of scalar,
        Input to be integrated.
    xx : ArrayLike of scalar,
        The sample points corresponding to the `yy` values.
        This must be either be shaped as
        * the same number of dimensions as `yy`, with the same length along the `axis` dimension, or
        * 1D with length matching `yy[axis]`
    axis : int,
        The axis over which to integrate.

    Returns
    -------
    ct : ndarray of scalar,
        Cumulative trapezoid rule integration.

    """
    if np.ndim(xx) == 1:
        pass
    elif np.ndim(xx) == np.ndim(yy):
        xx = xx[axis]
    else:
        err = f"Bad shape for `xx` (xx.shape={np.shape(xx)}, yy.shape={np.shape(yy)})!"
        log.error(err)
        raise ValueError(err)
    ct = np.moveaxis(yy, axis, 0)
    ct = 0.5 * (ct[1:] + ct[:-1])
    ct = np.moveaxis(ct, 0, -1)
    ct = ct * np.diff(xx)
    if cumsum:
        ct = np.cumsum(ct, axis=-1)
    ct = np.moveaxis(ct, -1, axis)
    return ct


def _parse_log_norm_pars(vals, size, default=None):
    """Parse/Sanitize the parameters for a log-normal distribution.

    ()   ==> (N,)
    (2,) ==> (N,) log_normal(vals)
    (N,) ==> (N,)

    BUG: this function should probably be deprecated / removed !

    Parameters
    ----------
    vals : object,
        Input, can be a single value, (2,) array_like, of array_like of size `size`.
        scalar : this value is broadcast to an ndarray of size `size`
        (2,) array_like : these two arguments are passed to `log_normal_base_10` and `size` samples
                          are drawn
        (N,) array_like : if `N` matches `size`, these values are returned.

    Returns
    -------
    vals : ndarray
        Returned values.

    """
    if (vals is None):
        if default is None:
            return None
        vals = default

    if np.isscalar(vals):
        vals = vals * np.ones(size)
    elif (isinstance(vals, tuple) or isinstance(vals, list)) and (len(vals) == 2):
        vals = log_normal_base_10(*vals, size=size)
    elif np.shape(vals) != (size,):
        err = "`vals` must be scalar, (2,) of scalar, or array (nbins={},) of scalar!".format(size)
        raise ValueError(err)

    return vals


# =================================================================================================
# ====    General Astronomy    ====
# =================================================================================================


def dfdt_from_dadt(dadt, sepa, mtot=None, freq_orb=None):
    """Convert from hardening rate in separation to hardening rate in frequency.

    Parameters
    ----------
    dadt : array_like
        Hardening rate in terms of binary separation.
    sepa : array_like
        Binary separations.
    mtot : None or array_like
        Either `mtot` or `freq_orb` must be provided.
    freq_orb : None or array_like
        Either `mtot` or `freq_orb` must be provided.

    Returns
    -------
    dfdt :
        Hardening rate in terms of frequency.
        NOTE: Has the opposite sign as `dadt`.
    freq_orb :
        Orbital frequency, in the rest-frame

    """
    if (mtot is None) and (freq_orb is None):
        err = "Either `mtot` or `freq_orb` must be provided!"
        log.error(err)
        raise ValueError(err)
    if freq_orb is None:
        freq_orb = kepler_freq_from_sepa(mtot, sepa)

    dfdt = - 1.5 * (freq_orb / sepa) * dadt
    return dfdt, freq_orb


def mtmr_from_m1m2(m1, m2=None):
    """Convert from primary and secondary masses into total-mass and mass-ratio.

    NOTE: it doesn't matter if `m1` or `m2` is the primary or secondary.

    Parameters
    ----------
    m1 : array_like,
        Mass.  If this is a single value, or a 1D array, it denotes the mass of one component of
        a binary.  It can also be shaped, (N,2) where the two elements are the two component masses.
    m2 : None or array_like,
        If array_like, it must match the shape of `m1`, and corresponds to the companion mass.

    Returns
    -------
    (2,N) ndarray
        Total mass and mass-ratio.  If the input values are floats, this is just shaped (2,).

    """
    if m2 is not None:
        masses = np.stack([m1, m2], axis=-1)
    else:
        assert np.shape(m1)[-1] == 2, "If only `m1` is given, last dimension must be 2!"
        masses = np.asarray(m1)

    mtot = masses.sum(axis=-1)
    mrat = masses.min(axis=-1) / masses.max(axis=-1)
    return np.array([mtot, mrat])


def m1m2_from_mtmr(mt, mr):
    """Convert from total-mass and mass-ratio to individual masses.

    Parameters
    ----------
    mt : array_like
        Total mass of the binary.
    mr : array_like
        Mass ratio of the binary.

    Returns
    -------
    (2,N) ndarray
        Primary and secondary masses respectively.
        0-primary (more massive component),
        1-secondary (less massive component)

    """
    mt = np.asarray(mt)
    mr = np.asarray(mr)
    m1 = mt/(1.0 + mr)
    m2 = mt - m1
    return np.array([m1, m2])


def frst_from_fobs(fobs, redz):
    """Calculate rest-frame frequency from observed frequency and redshift.

    Parameters
    ----------
    fobs : array_like
        Observer-frame frequencies.
    redz : array_like
        Redshifts.

    Returns
    -------
    fobs : array_like
        Rest-frame frequencies.

    """
    frst = fobs * (1.0 + redz)
    return frst


def fobs_from_frst(frst, redz):
    """Calculate observed frequency from rest-frame frequency and redshift.

    Parameters
    ----------
    frst : array_like
        Rest-frame frequencies.
    redz : array_like
        Redshifts.

    Returns
    -------
    fobs : array_like
        Observer-frame frequencies.

    """
    fobs = frst / (1.0 + redz)
    return fobs


def kepler_freq_from_sepa(mass, sepa):
    """Calculate binary orbital frequency using Kepler's law.

    Parameters
    ----------
    mass : array_like
        Binary total mass [grams].
    sepa : array_like
        Binary semi-major axis or separation [cm].

    Returns
    -------
    freq : array_like
        Binary orbital frequency [1/s].

    """
    freq = (1.0/(2.0*np.pi))*np.sqrt(NWTG*mass)/np.power(sepa, 1.5)
    return freq


def kepler_sepa_from_freq(mass, freq):
    """Calculate binary separation using Kepler's law.

    Parameters
    ----------
    mass : array_like
        Binary total mass [grams]
    freq : array_like
        Binary orbital frequency [1/s].

    Returns
    -------
    sepa : array_like
        Binary semi-major axis (i.e. separation) [cm].

    """
    mass = np.asarray(mass)
    freq = np.asarray(freq)
    sepa = np.power(NWTG*mass/np.square(2.0*np.pi*freq), 1.0/3.0)
    return sepa


def rad_isco(m1, m2, factor=3.0):
    """Inner-most Stable Circular Orbit, radius at which binaries 'merge'.

    ENH: allow single (total) mass argument.
    ENH: add function to calculate factor as a function of BH spin.

    Parameters
    ----------
    m1 : array_like,
        Mass of first (either) component of binary [grams].
    m2 : array_like,
        Mass of second (other) component of binary [grams].
    factor : float,
        Factor by which to multiple the Schwarzschild radius to define the ISCO.
        3.0 for a non-spinning black-hole.

    Returns
    -------
    rs : array_like,
        Radius of the inner-most stable circular orbit [cm].

    """
    return factor * schwarzschild_radius(m1+m2)


def schwarzschild_radius(mass):
    """Return the Schwarschild radius [cm] for the given mass [grams].

    Parameters
    ----------
    m1 : array_like
        Mass [grams]

    Returns
    -------
    rs : array_like,
        Schwzrschild radius for this mass.

    """
    rs = SCHW * mass
    return rs


# =================================================================================================
# ====    Gravitational Waves    ====
# =================================================================================================


def chirp_mass(m1, m2=None):
    """Calculate the chirp-mass of a binary.

    Parameters
    ----------
    m1 : array_like,
        Mass [grams]
        This can either be the mass of the primary component, if scalar or 1D array_like,
        or the mass of both components, if 2D array_like, shaped (N, 2).
    m2 : None or array_like,
        Mass [grams] of the other component of the binary.  If given, the shape must be
        broadcastable against `m1`.

    Returns
    -------
    mc : array_like,
        Chirp mass [grams] of the binary.

    """
    # (N, 2)  ==>  (N,), (N,)
    if m2 is None:
        m1, m2 = np.moveaxis(m1, -1, 0)
    mc = np.power(m1 * m2, 3.0/5.0)/np.power(m1 + m2, 1.0/5.0)
    return mc


def gw_char_strain(hs, dur_obs, freq_orb_obs, freq_orb_rst, dfdt):
    """GW Characteristic Strain.

    See, e.g., Sesana+2004, Eq.35
    NOTE: make sure this is the correct definition of "characteristic" strain for your application!

    Parameters
    ----------
    hs : array_like,
        Strain amplitude (e.g. `gw_strain()`, sky- and polarization- averaged) of the source.
    dur_obs : array_like,
        Duration of observations, in the observer frame.
    freq_orb_obs : array_like,
        Observer-frame orbital frequency.
    freq_orb_rst : array_like,
        Rest-frame orbital frequency.
    dfdt : array_like,
        Rate of frequency evolution of the binary, in the rest-frame.

    Returns
    -------
    hc : array_like,
        Characteristic strain of the binary.

    """

    ncycles = freq_orb_rst**2 / dfdt
    ncycles = np.clip(ncycles, None, dur_obs * freq_orb_obs)
    hc = hs * np.sqrt(ncycles)
    return hc


def gw_dedt(m1, m2, sepa, eccen):
    """GW Eccentricity Evolution rate (de/dt) due to GW emission.

    NOTE: returned value is negative.

    See Peters 1964, Eq. 5.8
    http://adsabs.harvard.edu/abs/1964PhRv..136.1224P

    Parameters
    ----------
    m1 : array_like,
        Mass of one component of the binary [grams].
    m2 : array_like,
        Mass of other component of the binary [grams].
    sepa : array_like,
        Binary semi-major axis (i.e. separation) [cm].
    eccen : array_like,
        Binary orbital eccentricity.

    Returns
    -------
    dedt : array_like
        Rate of eccentricity change of the binary.
        NOTE: returned value is negative or zero.

    """
    cc = _GW_DEDT_ECC_CONST
    e2 = eccen**2
    dedt = cc * m1 * m2 * (m1 + m2) / np.power(sepa, 4)
    dedt *= (1.0 + e2*121.0/304.0) * eccen / np.power(1 - e2, 5.0/2.0)
    return dedt


def gw_dade(m1, m2, sepa, eccen):
    """Rate of semi-major axis evolution versus eccentricity, due to GW emission (da/de).

    NOTE: returned value is positive (e and a go in same direction).
    See [Peters1964]_, Eq. 5.7

    Parameters
    ----------
    m1 : array_like
        Mass of one component of the binary [grams].
    m2 : array_like
        Mass of other component of the binary [grams].
    sepa : array_like
        Binary semi-major axis (separation) [grams].
    eccen : array_like
        Binary eccentricity [grams].

    Returns
    -------
    dade : array_like
        Rate of change of semi-major axis versus eccentricity [cm].
        NOTE: returned value is positive.

    """
    e2 = eccen**2
    num = (1 + (73.0/24.0)*e2 + (37.0/96.0)*e2*e2)
    den = (1 - e2) * (1.0 + (121.0/304.0)*e2)
    dade = (12.0 / 19.0) * (sepa / eccen) * (num / den)
    return dade


def gw_freq_dist_func(nn, ee=0.0):
    """GW frequency distribution function.

    See [EN07]_ Eq. 2.4; this function gives g(n,e).

    BUG: use recursion relation when possible,
         J_{n-1}(x) + J_{n+1}(x) = (2n/x) J_n(x)

    Parameters
    ----------
    nn : int,
        Number of frequency harmonic to calculate.
    ee : array_like,
        Binary eccentricity.

    Returns
    -------
    gg : array_like,
        GW Frequency distribution function g(n,e).

    """
    import scipy as sp
    import scipy.special  # noqa

    # Calculate with non-zero eccentrictiy
    bessel = sp.special.jn
    ne = nn*ee
    n2 = np.square(nn)
    jn_m2 = bessel(nn-2, ne)
    jn_m1 = bessel(nn-1, ne)

    # Use recursion relation:
    jn = (2*(nn-1) / ne) * jn_m1 - jn_m2
    jn_p1 = (2*nn / ne) * jn - jn_m1
    jn_p2 = (2*(nn+1) / ne) * jn_p1 - jn

    aa = np.square(jn_m2 - 2.0*ee*jn_m1 + (2/nn)*jn + 2*ee*jn_p1 - jn_p2)
    bb = (1 - ee*ee)*np.square(jn_m2 - 2*ee*jn + jn_p2)
    cc = (4.0/(3.0*n2)) * np.square(jn)
    gg = (n2*n2/32) * (aa + bb + cc)
    return gg


def gw_hardening_rate_dadt(m1, m2, sepa, eccen=None):
    """GW Hardening rate in separation (da/dt).

    NOTE: returned value is negative.

    See [Peters1964]_, Eq. 5.6

    Parameters
    ----------
    m1 : array_like,
        Mass of one component of the binary [grams].
    m2 : array_like,
        Mass of other component of the binary [grams].
    sepa : array_like,
        Binary semi-major axis (i.e. separation) [cm].
    eccen : None or array_like,
        Binary orbital eccentricity.  Treated as zero if `None`.

    Returns
    -------
    dadt : array_like,
        Binary hardening rate [cm/s] due to GW emission.

    """
    cc = _GW_DADT_SEP_CONST
    dadt = cc * m1 * m2 * (m1 + m2) / np.power(sepa, 3)
    if eccen is not None:
        fe = _gw_ecc_func(eccen)
        dadt *= fe
    return dadt


def gw_hardening_rate_dfdt(m1, m2, freq_orb, eccen=None):
    """GW Hardening rate in frequency (df/dt).

    Parameters
    ----------
    m1 : array_like
        Mass of one component of each binary [grams].
    m2 : array_like
        Mass of other component of each binary [grams].
    freq_orb : array_like
        Rest frame orbital frequency of each binary [1/s].
    eccen : array_like, optional
        Eccentricity of each binary.

    Returns
    -------
    dfdt : array_like,
        Hardening rate in terms of frequency for each binary [1/s^2].

    """
    sepa = kepler_sepa_from_freq(m1+m2, freq_orb)
    dfdt = gw_hardening_rate_dadt(m1, m2, sepa, eccen=eccen)
    # dfdt, _ = dfdt_from_dadt(dfdt, sepa, mtot=m1+m2)
    dfdt, _ = dfdt_from_dadt(dfdt, sepa, freq_orb=freq_orb)
    return dfdt, freq_orb


def gw_hardening_timescale_freq(mchirp, frst):
    """GW Hardening timescale in terms of frequency (not separation).

    ``tau = f_r / (df_r / dt)``, e.g. [EN07]_ Eq.2.9

    Parameters
    ----------
    mchirp : array_like,
        Chirp mass in [grams]
    frst : array_like,
        Rest-frame orbital frequency [1/s].

    Returns
    -------
    tau : array_like,
        GW hardening timescale defined w.r.t. orbital frequency [sec].

    """
    tau = (5.0 / 96.0) * np.power(NWTG*mchirp/SPLC**3, -5.0/3.0) * np.power(2*np.pi*frst, -8.0/3.0)
    return tau


def gw_lum_circ(mchirp, freq_orb_rest):
    """Calculate the GW luminosity of a circular binary.

    [EN07]_ Eq. 2.2

    Parameters
    ----------
    mchirp : array_like,
        Binary chirp mass [grams].
    freq_orb_rest : array_like,
        Rest-frame binary orbital frequency [1/s].

    Returns
    -------
    lgw_circ : array_like,
        GW Luminosity [erg/s].

    """
    lgw_circ = _GW_LUM_CONST * np.power(2.0*np.pi*freq_orb_rest*mchirp, 10.0/3.0)
    return lgw_circ


def gw_strain_source(mchirp, dcom, freq_orb_rest):
    """GW Strain from a single source in a circular orbit.

    See: [Sesana2004]_ Eq.36 or [Enoki2004]_ Eq.5.

    Parameters
    ----------
    mchirp : array_like,
        Binary chirp mass [grams].
    dcom : array_like,
        Comoving distance to source [cm].
    freq_orb_rest : array_like,
        Rest-frame binary orbital frequency [1/s].

    Returns
    -------
    hs : array_like,
        GW Strain (*not* characteristic strain).

    """
    hs = _GW_SRC_CONST * mchirp * np.power(2*mchirp*freq_orb_rest, 2/3) / dcom
    return hs


def sep_to_merge_in_time(m1, m2, time):
    """The initial separation required to merge within the given time.

    See: [Peters1964]_

    Parameters
    ----------
    m1 : array_like,
        Mass of one component of the binary [grams].
    m2 : array_like,
        Mass of other component of the binary [grams].
    time : array_like,
        The duration of time of interest [sec].

    Returns
    -------
    array_like
        Initial binary separation [cm].

    """
    GW_CONST = 64*np.power(NWTG, 3.0)/(5.0*np.power(SPLC, 5.0))
    a1 = rad_isco(m1, m2)
    return np.power(GW_CONST*m1*m2*(m1+m2)*time - np.power(a1, 4.0), 1./4.)


def time_to_merge_at_sep(m1, m2, sepa):
    """The time required to merge starting from the given initial separation.

    See: [Peters1964]_.

    Parameters
    ----------
    m1 : array_like,
        Mass of one component of the binary [grams].
    m2 : array_like,
        Mass of other component of the binary [grams].
    sepa : array_like,
        Binary semi-major axis (i.e. separation) [cm].

    Returns
    -------
    array_like
        Duration of time for binary to coalesce [sec].

    """
    GW_CONST = 64*np.power(NWTG, 3.0)/(5.0*np.power(SPLC, 5.0))
    a1 = rad_isco(m1, m2)
    delta_sep = np.power(sepa, 4.0) - np.power(a1, 4.0)
    return delta_sep/(GW_CONST*m1*m2*(m1+m2))


def _gw_ecc_func(eccen):
    """GW Hardening rate eccentricitiy dependence F(e).

    See [Peters1964]_ Eq. 5.6, or [EN07]_ Eq. 2.3

    Parameters
    ----------
    eccen : array_like,
        Binary orbital eccentricity [].

    Returns
    -------
    fe : array_like
        Eccentricity-dependence term of GW emission [].

    """
    e2 = eccen*eccen
    num = 1 + (73/24)*e2 + (37/96)*e2*e2
    den = np.power(1 - e2, 7/2)
    fe = num / den
    return fe
