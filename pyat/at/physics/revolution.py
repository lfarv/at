from ..lattice import Lattice, get_rf_frequency, check_radiation, get_s_pos
from ..lattice import DConstant
from ..constants import clight
from ..tracking import lattice_pass
from .orbit import find_orbit4
import numpy
import functools

__all__ = ['frequency_control', 'get_mcf', 'get_slip_factor',
           'get_revolution_frequency', 'set_rf_frequency']


def frequency_control(func):
    """Function to be used as decorator for ``func(ring, *args, **kwargs)``

    If ``ring.radiation`` is ``True`` and ``dp``, ``dct`` or ``df`` is
    specified, make a copy of ``ring`` with a modified RF frequency, remove
    ``dp``, ``dct`` or ``df`` from ``kwargs`` and call ``func`` with the
    modified ``ring``.

    If ``ring.radiation`` is ``False``, ``func`` is called unchanged.

    Examples::

        @frequency_control
        def func(ring, *args, dp=None, dct=None, **kwargs):
            pass
    """
    @functools.wraps(func)
    def wrapper(ring, *args, **kwargs):
        if ring.radiation:
            momargs = {}
            for key in ['dp', 'dct', 'df']:
                v = kwargs.pop(key, None)
                if v is not None:
                    momargs[key] = v
            if len(momargs) > 0:
                ring = set_rf_frequency(ring, **momargs, copy=True)
        return func(ring, *args, **kwargs)
    return wrapper


@check_radiation(False)
def get_mcf(ring, dp=0.0, keep_lattice=False, **kwargs):
    """Compute the momentum compaction factor

    PARAMETERS
        ring            lattice description (radiation must be OFF)

    KEYWORDS
        dp=0.0          momentum deviation.
        keep_lattice    Assume no lattice change since the previous tracking.
                        Defaults to False
        dp_step=1.0E-6  momentum deviation used for differentiation
    """
    dp_step = kwargs.pop('DPStep', DConstant.DPStep)
    fp_a, _ = find_orbit4(ring, dp=dp - 0.5*dp_step, keep_lattice=keep_lattice)
    fp_b, _ = find_orbit4(ring, dp=dp + 0.5*dp_step, keep_lattice=True)
    fp = numpy.stack((fp_a, fp_b),
                     axis=0).T  # generate a Fortran contiguous array
    b = numpy.squeeze(lattice_pass(ring, fp, keep_lattice=True), axis=(2, 3))
    ring_length = get_s_pos(ring, len(ring))
    alphac = (b[5, 1] - b[5, 0]) / dp_step / ring_length[0]
    return alphac


def get_slip_factor(ring, **kwargs):
    """Compute the slip factor

    PARAMETERS
        ring            lattice description (radiation must be OFF)

    KEYWORDS
        dp=0.0          momentum deviation.
        keep_lattice    Assume no lattice change since the previous tracking.
                        Defaults to False
        dp_step=1.0E-6  momentum deviation used for differentiation
    """
    gamma = ring.gamma
    etac = (1.0/gamma/gamma - get_mcf(ring, **kwargs))
    return etac


def get_revolution_frequency(ring, dp=None, dct=None):
    """Compute the revolution frequency of the full ring [Hz]

    PARAMETERS
        ring            lattice description

    KEYWORDS
        dp=0.0          momentum deviation.
        dct=0.0         Path length deviation
    """
    lcell = ring.get_s_pos(len(ring))[0]
    frev = ring.beta * clight / lcell / ring.periodicity
    if dct is not None:
        frev *= lcell / (lcell + dct)
    elif dp is not None:
        # Find the path lengthening for dp
        rnorad = ring.radiation_off(copy=True) if ring.radiation else ring
        orbit = lattice_pass(rnorad, rnorad.find_orbit4(dp=dp)[0])
        dct = numpy.squeeze(orbit)[5]
        frev *= lcell / (lcell + dct)
    return frev


def set_rf_frequency(ring, frequency=None, dp=None, dct=None, **kwargs):
    """Set the RF frequency

    PARAMETERS
        ring            lattice description
        frequency       RF frequency [Hz]. Default: nominal frequency.

    KEYWORDS
        dp=0.0          Momentum deviation.
        dct=0.0         Path length deviation
        cavpts=None     If None, look for ring.cavpts, or otherwise take all
                        cavities.
        array=False     If False, frequency is applied to the selected cavities
                        with the lowest frequency. The frequency of all the
                        other selected cavities is scaled by the same ratio.
                        If True, directly apply frequency to the selected
                        cavities. The value must be broadcastable to the number
                        of cavities.
        copy=False      If True, returns a shallow copy of ring with new
                        cavity elements. Otherwise, modify ring in-place
    """
    if frequency is None:
        frequency = ring.get_revolution_frequency(dp=dp, dct=dct) \
                    * ring.harmonic_number
    return ring.set_cavity(Frequency=frequency, **kwargs)


Lattice.mcf = property(get_mcf, doc="Momentum compaction factor")
Lattice.slip_factor = property(get_slip_factor, doc="Slip factor")
Lattice.get_revolution_frequency = get_revolution_frequency
Lattice.get_mcf = get_mcf
Lattice.get_slip_factor = get_slip_factor
Lattice.set_rf_frequency = set_rf_frequency
Lattice.rf_frequency = property(get_rf_frequency, set_rf_frequency,
    doc="Fundamental RF frequency [Hz]. The special value "
        ":py:class:`at.Frf.NOMINAL <at.lattice.cavity_access.Frf>` "
        "means nominal frequency.")
