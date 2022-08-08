"""Tests for the :mod:`holodeck.evolution` submodule.
"""

import numpy as np
import pytest

import holodeck as holo
import holodeck.population
import holodeck.evolution
from holodeck.constants import GYR, MSOL, KPC, YR, PC

TIME = 2.0 * GYR


def test_init_generic_evolution():
    """Check that instantiation of a generic evolution class succeeds and fails as expected.
    """

    SIZE = 10

    class Good_Pop(holo.population._Population_Discrete):

        def _init(self):
            self.mass = np.zeros((SIZE, 2))
            self.sepa = np.zeros(SIZE)
            self.scafa = np.zeros(SIZE)
            return

    class Good_Hard(holo.evolution._Hardening):

        def dadt_dedt(self, *args, **kwargs):
            return 0.0

    pop = Good_Pop()
    hard = Good_Hard()
    holo.evolution.Evolution(pop, hard)
    holo.evolution.Evolution(pop, [hard])

    with pytest.raises(TypeError):
        holo.evolution.Evolution(pop, pop)

    with pytest.raises(TypeError):
        holo.evolution.Evolution(hard, hard)

    with pytest.raises(TypeError):
        holo.evolution.Evolution(pop, None)

    with pytest.raises(TypeError):
        holo.evolution.Evolution(None, hard)

    return


@pytest.fixture(scope='session')
def evolution_illustris_fixed_time_circ():
    pop = holo.population.Pop_Illustris()
    fixed = holo.evolution.Fixed_Time.from_pop(pop, TIME)
    evo = holo.evolution.Evolution(pop, fixed, nsteps=30)
    evo.evolve()
    return evo


@pytest.fixture(scope='session')
def evolution_illustris_fixed_time_eccen():
    ecc = holo.population.PM_Eccentricity()
    pop = holo.population.Pop_Illustris(mods=ecc)
    fixed = holo.evolution.Fixed_Time.from_pop(pop, TIME)
    evo = holo.evolution.Evolution(pop, fixed, nsteps=30)
    evo.evolve()
    return evo


@pytest.fixture(scope='session')
def evo_def():
    ecc = holo.population.PM_Eccentricity()
    pop = holo.population.Pop_Illustris(mods=ecc)
    fixed = holo.evolution.Fixed_Time.from_pop(pop, TIME)
    evo = holo.evolution.Evolution(pop, fixed, nsteps=30)

    assert evo._evolved is False
    with pytest.raises(RuntimeError):
        evo._check_evolved()

    evo.evolve()
    assert evo._evolved is True
    evo._check_evolved()
    return evo


@pytest.fixture(scope='session')
def simplest():
    SIZE = 100

    class Pop(holo.population._Population_Discrete):
        def _init(self):
            self.mass = (10.0 ** np.random.uniform(6, 10, (SIZE, 2))) * MSOL
            self.sepa = (10.0 ** np.random.uniform(1, 3, SIZE)) * 1e3 * PC
            self.scafa = np.random.uniform(0.25, 0.75, SIZE)
            self.eccen = np.random.uniform(0.4, 0.6, SIZE)
            return

    class Hard(holo.evolution._Hardening):
        def dadt_dedt(self, evo, step, *args, **kwargs):
            dadt = -(PC/YR) * np.ones(evo.size)
            dedt = None
            return dadt, dedt

    pop = Pop()
    hard = Hard()
    evo = holo.evolution.Evolution(pop, hard)

    return evo


class Test_Illustris_Fixed:

    def _test_has_keys(self, evolution_illustris_fixed_time_circ):
        evo = evolution_illustris_fixed_time_circ
        # Make sure evolution attributes all exist
        keys = ['mass', 'sepa', 'eccen', 'scafa', 'tlook', 'dadt', 'dedt']
        for kk in keys:
            assert kk in evo._EVO_PARS, f"Missing attribute key '{kk}' in evolution instance!"

    def test_has_derived_keys(self, evolution_illustris_fixed_time_eccen):
        evo = evolution_illustris_fixed_time_eccen
        # Make sure evolution attributes all exist
        keys = ['mass', 'sepa', 'eccen', 'scafa', 'tlook', 'dadt', 'dedt']
        positive = ['mass', 'sepa', 'eccen', 'scafa', ]
        for kk in keys:
            vv = getattr(evo, kk)

            err = f"Attribute '{kk}' has non-finite values: {holo.utils.stats(vv)}"
            assert np.all(np.isfinite(vv)), err

            if kk in positive:
                err = f"Attribute '{kk}' has <= 0.0 values: {holo.utils.stats(vv)}"
                assert np.all(vv > 0.0), err

        return

    def test_has_keys_circ(self, evolution_illustris_fixed_time_circ):
        self._test_has_keys(evolution_illustris_fixed_time_circ)

    def test_has_keys_eccen(self, evolution_illustris_fixed_time_eccen):
        self._test_has_keys(evolution_illustris_fixed_time_eccen)

    def _test_evo_init(self, evo, eccen):
        # Make sure population attributes are initialized correctly
        keys = ['mass', 'sepa', 'scafa']
        if eccen:
            keys.append('eccen')

        for kk in keys:
            evo_val = getattr(evo, kk)
            pop_val = getattr(evo._pop, kk)

            # Compare evo 0th step values to initial population
            assert np.allclose(evo_val[:, 0], pop_val), f"population and evolution '{kk}' values do not match!"
            # make sure all values are non-zero and finite
            assert np.all(evo_val > 0.0) and np.all(np.isfinite(evo_val)), f"Found '{kk}' <= 0.0 values!"

        # Make sure eccentricity is not set or evolved
        if not eccen:
            assert evo.eccen is None
            assert evo.dedt is None
        return

    def test_evo_init_circ(self, evolution_illustris_fixed_time_circ):
        self._test_evo_init(evolution_illustris_fixed_time_circ, eccen=False)

    def test_evo_init_eccen(self, evolution_illustris_fixed_time_eccen):
        self._test_evo_init(evolution_illustris_fixed_time_eccen, eccen=True)

    def _test_evo_time(self, evo):
        # Make sure lifetimes are close to target
        time = evo.tlook
        dt = time[:, 0] - time[:, -1]
        ave = dt.mean()
        std = dt.std()
        assert np.isclose(ave, TIME, rtol=0.25), f"Mean dt differs significantly from input!  {ave/TIME:.4e}"
        assert (std/ave < 0.05), f"Significant variance in output dt values!  {std/ave:.4e}"

    def test_evo_time_circ(self, evolution_illustris_fixed_time_circ):
        self._test_evo_time(evolution_illustris_fixed_time_circ)

    def test_evo_time_eccen(self, evolution_illustris_fixed_time_eccen):
        self._test_evo_time(evolution_illustris_fixed_time_eccen)


class Test_Evolution_Basic:

    def test_tage(self, evo_def):
        evo = evo_def

        tage = evo.tage
        assert tage.shape == evo.tlook.shape

        check = holo.cosmo.age(0.0).cgs.value - evo.tlook
        assert np.allclose(tage, check)
        return

    def test_mtmr(self, evo_def):
        evo = evo_def

        mt, mr = evo.mtmr
        assert mt.shape == evo.sepa.shape
        assert mr.shape == evo.sepa.shape

        mass = evo.mass
        assert mass.shape == (evo.size, evo.steps, 2)
        mass = np.moveaxis(mass, -1, 0)
        mt_check, mr_check = holo.utils.mtmr_from_m1m2(*mass)
        assert np.all(mt == mt_check)
        assert np.all(mr == mr_check)

        return


class Test_Evolution_Advanced:

    _EVO_PARS = ['mass', 'sepa', 'eccen', 'scafa', 'tlook', 'dadt', 'dedt']
    _PARS_POSITIVE = ['mass', 'sepa', 'eccen', 'scafa']

    def test_at_failures(self, evo_def):
        evo = evo_def

        # Make sure single, and iterable values work
        xpar = 'fobs'
        evo.at(xpar, [1/YR, 2/YR])
        evo.at(xpar, [1/YR])
        evo.at(xpar, 1/YR)
        evo.at(xpar, 1/YR, params=['sepa', 'scafa'])
        evo.at(xpar, 1/YR, params=['mass'])
        evo.at(xpar, 1/YR, params='mass')

        xpar = 'sepa'
        evo.at(xpar, [1*PC, 2*PC])
        evo.at(xpar, [1*PC])
        evo.at(xpar, 1*PC)
        evo.at(xpar, 1*PC, params=['mass', 'scafa'])
        evo.at(xpar, 1*PC, params=['mass'])
        evo.at(xpar, 1*PC, params='mass')

        fobs = np.logspace(-2, 1, 4) / YR
        # sepa = np.logspace(-2, 2, 5) * PC

        # use invalid 'xpar' name ('mass')
        with pytest.raises(ValueError, match='`xpar` must be one of '):
            evo.at('mass', fobs)

        with pytest.raises(ValueError, match='`targets` extrema'):
            evo.at('fobs', 1e20/YR)

        with pytest.raises(ValueError, match='`targets` extrema'):
            evo.at('sepa', 1e6*PC)

        with pytest.raises(ValueError, match='`targets` extrema'):
            evo.at('sepa', 1e-10*PC)

        return

    def test_at_fobs_all(self, evo_def):
        evo = evo_def
        xpar = 'fobs'
        coal = False

        # Choose interpolation targets
        fobs = np.logspace(-3, 0, 9) / YR
        numx = fobs.size
        # For a moderate range of frequencies (after formation, before coalescence), then all values
        # should be finite (`nan`s are returned either before formation, or after coalescence)
        FINITE_FLAG = True
        print(f"{fobs*YR}")
        vals = evo.at(xpar, fobs, coal=coal)
        print(f"received `at` vals with keys: {vals.keys()}!")

        for par in self._EVO_PARS:
            # Make sure parameter is also included in `evolution` instance's list of parameters
            assert par in evo._EVO_PARS
            # Make sure parameter is actually returned
            assert par in vals, f"'{par}' missing from returned `at` dictionary!"

            # Check shape, should be (N, X) N-binaries, X-targets, except for `mass` which is (N, X, 2)
            vv = vals[par]
            assert vv.shape[0] == evo.size
            assert vv.shape[1] == numx
            assert np.ndim(vv) == 2 or np.shape(vv)[2] == 2

            if FINITE_FLAG:
                err = f"{par} found {holo.utils.frac_str(~np.isfinite(vv))} non-finite values!"
                assert np.all(np.isfinite(vv)), err

            # Make sure values are positive when they should be
            if par in self._PARS_POSITIVE:
                print(par, np.all(vv > 0.0), holo.utils.frac_str(vv > 0.0), np.any(vv <= 0.0), np.any(~np.isfinite(vv)))
                assert np.all(vv > 0.0), f"{par} values found to be non-positive ({holo.utils.frac_str(vv > 0.0)})!"

        for par in evo._EVO_PARS:
            assert par in vals, f"'{par}' missing from returned `at` dictionary!"

        # Choose interpolation targets
        # 0th element here should be within evolution range, while 1th element should be after coalesence -> `nan` vals
        fobs = np.array([0.1, 1e6]) / YR
        print(f"fobs = {fobs*YR} [1/yr]")
        vals = evo.at(xpar, fobs, coal=coal)

        for ii in range(2):
            msg = "all values should be "
            msg += "finite" if ii == 0 else "non-finite"
            for kk, vv in vals.items():
                vv = vv[:, ii]
                test = np.isfinite(vv) if ii == 0 else ~np.isfinite(vv)
                err = f"{kk} {msg}, good={holo.utils.frac_str(test)} | bad={holo.utils.frac_str(~test)}"
                print(err)
                assert np.all(test), err

    def test_at_sepa_coal(self, evo_def):
        evo = evo_def
        xpar = 'sepa'
        coal = True

        # Choose interpolation targets
        sepa = 1e1 * PC
        vals = evo.at(xpar, sepa, coal=coal)

        ncoal = np.count_nonzero(evo.coal)
        ntot = evo.size
        assert ncoal < ntot, f"This test requires that not all binaries are coalescing ({ncoal}/{ntot})!"

        vv = vals['sepa']

        assert vv.shape[0] == ntot
        assert np.count_nonzero(np.isfinite(vv)) == ncoal
        assert np.all(np.isfinite(vv) == evo.coal)

        # ---- make sure the right values are finite and non-finite
        sel = (evo.scafa[:, -1] < 1.0)

        def fstr(xx):
            return holo.utils.frac_str(xx, 8)

        # make sure returned `at` values are all finite for coalescing systems
        yesfin = np.isfinite(vv[sel])
        msg = f"{fstr(sel)} systems are coalescing, `at` samples should be finite: {fstr(yesfin)}"
        print(msg)
        assert np.all(yesfin), msg

        # make sure returned `at` values are all non-finite for non-coalescing systems
        notfin = ~np.isfinite(vv[~sel])
        msg = f"{fstr(~sel)} systems are stalling  , `at` samples should be non-finite: {fstr(notfin)}"
        print(msg)
        assert np.all(notfin), msg

        return

    def test_at_sepa_all(self, evo_def):
        evo = evo_def
        xpar = 'sepa'
        coal = False

        # Choose interpolation targets
        sepa = np.logspace(-1, 3, 8) * PC
        numx = sepa.size
        # For a moderate range of frequencies (after formation, before coalescence), then all values
        # should be finite (`nan`s are returned either before formation, or after coalescence)
        FINITE_FLAG = True
        print(f"sepa/PC = {sepa/PC}")
        vals = evo.at(xpar, sepa, coal=coal)
        print(f"received `at` vals with keys: {vals.keys()}!")

        for par in self._EVO_PARS:
            # Make sure parameter is also included in `evolution` instance's list of parameters
            assert par in evo._EVO_PARS
            # Make sure parameter is actually returned
            assert par in vals, f"'{par}' missing from returned `at` dictionary!"

            # Check shape, should be (N, X) N-binaries, X-targets, except for `mass` which is (N, X, 2)
            vv = vals[par]
            assert vv.shape[0] == evo.size
            assert vv.shape[1] == numx
            assert np.ndim(vv) == 2 or np.shape(vv)[2] == 2

            if FINITE_FLAG:
                err = f"{par} found {holo.utils.frac_str(~np.isfinite(vv))} non-finite values!"
                assert np.all(np.isfinite(vv)), err

            # Make sure values are positive when they should be
            if par in self._PARS_POSITIVE:
                print(par, np.all(vv > 0.0), holo.utils.frac_str(vv > 0.0), np.any(vv <= 0.0), np.any(~np.isfinite(vv)))
                assert np.all(vv > 0.0), f"{par} values found to be non-positive ({holo.utils.frac_str(vv > 0.0)})!"

        for par in evo._EVO_PARS:
            assert par in vals, f"'{par}' missing from returned `at` dictionary!"

        # Choose interpolation targets
        # 0th element here should be within evolution range, while 1th element should be after coalesence -> `nan` vals
        sepa = np.array([1e6, 0.1, 1e-8]) * PC
        print(f"sepa/PC = {sepa/PC}")
        vals = evo.at(xpar, sepa, coal=coal)

        for ii in range(2):
            msg = "all values should be "
            msg += "finite" if ii == 1 else "non-finite"
            for kk, vv in vals.items():
                vv = vv[:, ii]
                test = np.isfinite(vv) if ii == 1 else ~np.isfinite(vv)
                err = f"{kk} {msg}, good={holo.utils.frac_str(test)} | bad={holo.utils.frac_str(~test)}"
                print(err)
                assert np.all(test), err

        return


def mockup_modified():

    SIZE = 123

    class Pop(holo.population._Population_Discrete):

        def _init(self):
            self.mass = (10.0 ** np.random.uniform(6, 10, (SIZE, 2))) * MSOL
            self.sepa = (10.0 ** np.random.uniform(1, 3, SIZE)) * KPC
            self.scafa = np.random.uniform(0.25, 0.75, SIZE)
            return

    class Hard(holo.evolution._Hardening):

        def dadt_dedt(self, evo, step, *args, **kwargs):
            dadt = -(PC/YR) * np.ones(evo.size)
            dedt = None
            return dadt, dedt

    class Mod(holo.utils._Modifier):

        def modify(self, base):
            base.mass[...] = 0.0

    pop = Pop()
    hard = Hard()
    mod = Mod()
    evo = holo.evolution.Evolution(pop, hard, mods=mod)
    return evo


class Test_Modified:

    KEYS = ['sepa', 'mass', 'scafa']

    def test_uninit_without_evolving(self):
        evo = mockup_modified()

        for kk in self.KEYS:
            vv = getattr(evo, kk)
            assert np.all(vv[...] == 0.0)

        return

    def test_modified_after_evolved(self):
        evo = mockup_modified()
        print("before evolving, make sure all values are zero")
        for kk in self.KEYS:
            vv = getattr(evo, kk)
            assert np.all(vv[...] == 0.0)

        evo.evolve()
        print("after evolving, make sure non-modified values are non-zero")
        assert np.all(evo.sepa > 0.0)
        assert np.all(evo.scafa > 0.0)
        print("after evolving, make sure modified (sets mass to zero) took effect")
        assert np.all(evo.mass == 0.0)
        return


# ==============================================================================
# ====    Hardening Classes and Functions    ====
# ==============================================================================


class Test_Hardening_Generic:
    """Make sure that the :class:`evolution._Hardening` base-class behaves correctly.
    """

    def test_subclassing(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            holo.evolution._Hardening()

        # Without overriding `dadt_dedt` method, `TypeError` raises on instantiation
        class Hard_Fail(holo.evolution._Hardening):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Hard_Fail()

        # Overriding `dadt_dedt` method, instantiation allowed
        class Hard_Succeed(holo.evolution._Hardening):
            def dadt_dedt(self, evo, step):
                pass

        Hard_Succeed()
        return

    def test_simplest_subclass(self, simplest):
        evo = simplest
        evo.evolve()

        msg = "`Evolution.tage` should always be increasing!"
        print(msg)
        assert np.all(np.diff(evo.tage, axis=-1) >= 0.0), msg

        msg = "`Evolution.sepa` should always be decreasing!"
        print(msg)
        assert np.all(np.diff(evo.sepa, axis=-1) < 0.0)

        return


class Test_Hard_GW:
    """Test the :class:`evolution.Hard_GW` class.
    """

    def test_static_methods(self, simplest):
        evo = simplest
        evo.evolve()

        step = np.random.randint(evo.steps)
        print(f"step = {step}")
        dadt, dedt = holo.evolution.Hard_GW.dadt_dedt(evo, step)
        assert np.shape(dadt) == (evo.size,)
        assert np.shape(dedt) == (evo.size,)
        assert np.all(dadt <= 0.0)
        assert np.all(dedt <= 0.0)

        mt, mr = [mm[:, step] for mm in evo.mtmr]
        aa = evo.sepa[:, step]
        ee = evo.eccen[:, step]

        # Make sure combined method matches individual methods
        _dadt = holo.evolution.Hard_GW.dadt(mt, mr, aa, eccen=ee)
        _dedt = holo.evolution.Hard_GW.dedt(mt, mr, aa, eccen=ee)

        assert np.shape(dadt) == np.shape(_dadt)
        assert np.shape(dedt) == np.shape(_dedt)
        assert np.allclose(dadt, _dadt, rtol=1e-10)
        assert np.allclose(dedt, _dedt, rtol=1e-10)

        # Make sure combined method matches `utils` GW methods
        _dadt = holo.evolution.Hard_GW.dadt(mt, mr, aa, eccen=ee)
        _dedt = holo.evolution.Hard_GW.dedt(mt, mr, aa, eccen=ee)

        assert np.shape(dadt) == np.shape(_dadt)
        assert np.shape(dedt) == np.shape(_dedt)
        assert np.allclose(dadt, _dadt, rtol=1e-10)
        assert np.allclose(dedt, _dedt, rtol=1e-10)

        return


class Test_Sesana_Scattering:

    def test_basics(self):
        SIZE = 6
        mmbulge = holo.relations.MMBulge_KH2013()
        msigma = holo.relations.MSigma_KH2013()
        mass = (10.0 ** np.random.uniform(6, 10, (SIZE, 2))) * MSOL
        sepa = (10.0 ** np.random.uniform(1, 3, SIZE)) * PC

        kwargs_list = [
            dict(),
            dict(gamma_dehnen=0.5),
            dict(mmbulge=mmbulge),
            dict(msigma=msigma),
            dict(mmbulge=mmbulge, msigma=msigma),
        ]

        for eccen in [None, np.random.uniform(0.0, 1.0, sepa.size)]:
            print(f"\neccen = {eccen}")
            for kw in kwargs_list:
                print(f"kw = {kw}")
                sc = holo.evolution.Sesana_Scattering(**kw)
                dadt, dedt = sc._dadt_dedt(mass, sepa, eccen)
                print(f"dadt = {dadt}")
                print(f"dedt = {dedt}")
                assert np.shape(dadt) == np.shape(sepa)
                assert np.all(dadt < 0.0)

                if eccen is None:
                    assert dedt is None
                else:
                    assert np.shape(dedt) == np.shape(sepa)
                    assert np.all(dadt < 0.0)

        return


class Test_Dynamical_Friction_NFW:

    def test_basics(self):
        SIZE = 600
        mmbulge = holo.relations.MMBulge_KH2013()
        msigma = holo.relations.MSigma_KH2013()
        mass = (10.0 ** np.random.uniform(6, 9, (SIZE, 2))) * MSOL
        sepa = (10.0 ** np.random.uniform(1, 3, SIZE)) * PC
        redz = np.random.uniform(0.1, 2.0, SIZE)
        dt = 1e5 * YR

        print(f"mass[:, 0] = {mass[:, 0]}")
        print(f"mass[:, 1] = {mass[:, 1]}")
        print(f"sepa = {sepa}")
        print(f"redz = {redz}")
        print(f"dt = {dt}")

        kwargs_list = [
            dict(),
            dict(mmbulge=mmbulge),
            dict(msigma=msigma),
            dict(mmbulge=mmbulge, msigma=msigma),
        ]

        for eccen in [None, np.random.uniform(0.0, 1.0, sepa.size)]:
            for atten in [True, False]:
                print(f"\neccen = {eccen}, atten = {atten}")
                for kw in kwargs_list:
                    print(f"kw = {kw}")
                    df = holo.evolution.Dynamical_Friction_NFW(**kw)
                    dadt, dedt = df._dadt_dedt(mass, sepa, redz, dt, eccen, attenuate=atten)
                    print(f"dadt = {dadt}")
                    print(f"dedt = {dedt}")

                    bads = ~np.isfinite(dadt)
                    if np.any(bads):
                        print(f"FOUND BADS {holo.utils.frac_str(bads)}")
                        for kk, vv in dict(mass=mass, sepa=sepa, redz=redz, eccen=eccen).items():
                            if vv is None:
                                continue
                            print(f"{kk} :: {vv[bads]}")

                    assert np.shape(dadt) == np.shape(sepa)
                    assert np.all(dadt < 0.0)

                    if eccen is None:
                        assert dedt is None
                    else:
                        assert np.shape(dedt) == np.shape(sepa)
                        assert np.all(dedt == 0.0)

        return
