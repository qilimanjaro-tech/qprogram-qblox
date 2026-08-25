# Copyright 2026 Qilimanjaro Quantum Tech
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the ``qblox-default-v1`` capability profile.

These are the integration story of the package: every op the profile claims to support validates
clean against a :class:`~qprogram.PlatformCapabilities` that stacks ``qblox-default-v1`` on the bus
slot with the core-shipped ``qprogram-base-v1`` on the platform slot, and every constraint the
profile declares fires when violated. A core or vendor node that starts emitting a token neither
profile lists fails here.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from qprogram import QProgram
from qprogram.blocks import Average, Sweep
from qprogram.operations import Play
from qprogram.protocol import (
    BusCapabilities,
    CompilerCapabilities,
    Diagnostic,
    PlatformCapabilities,
    resolve_profile,
)
from qprogram.sweeps import Range, Values
from qprogram.validation import validate
from qprogram.waveforms import IQDrag, IQPair, Square

# Importing the package registers the qblox capability tokens and the profile bundle.
import qprogram_qblox
from qprogram_qblox.profiles import QBLOX_DEFAULT_V1

if TYPE_CHECKING:
    from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_caps(
    *,
    bus_limit_overrides: Mapping[str, float] | None = None,
    platform_limit_overrides: Mapping[str, float] | None = None,
) -> PlatformCapabilities:
    """Build a :class:`PlatformCapabilities` stacking the qblox bus profile on qprogram base.

    qblox is a real-time vendor, so its profile fills the bus slot's ``rt`` half and leaves the
    ``host`` half empty. The platform slot carries ``qprogram-base-v1`` in both halves, so a block
    lands on ``rt`` or ``host`` according to what its op-children require.
    """
    bus_cc = CompilerCapabilities.from_profile("qblox-default-v1", limit_overrides=bus_limit_overrides)
    platform_cc = CompilerCapabilities.from_profile(
        "qprogram-base-v1",
        limit_overrides=platform_limit_overrides,
    )
    bus_slot = BusCapabilities(rt=bus_cc, host=None)
    platform_slot = BusCapabilities(rt=platform_cc, host=platform_cc)
    return PlatformCapabilities(
        bus={},
        platform=platform_slot,
        default_bus_profile=bus_slot,
    )


def _diagnostics(p: QProgram, caps: PlatformCapabilities) -> list[Diagnostic]:
    """Validate and return just the diagnostic list (drops the plan)."""
    diagnostics, _ = validate(p, caps)
    return diagnostics


# ---------------------------------------------------------------------------
# Profile registration
# ---------------------------------------------------------------------------


def test_qblox_default_profile_is_registered() -> None:
    assert resolve_profile("qblox-default-v1") is QBLOX_DEFAULT_V1


def test_qblox_default_profile_carries_bus_side_tokens() -> None:
    """``qblox-default-v1`` is a bus profile: bus ops, waveforms, fields, ``vendor.qblox.*``."""
    caps = CompilerCapabilities.from_profile("qblox-default-v1")
    assert caps.profile == "qblox-default-v1"
    assert caps.version == (0, 1, 0)
    for token in (
        "op.play",
        "op.measure",
        "op.wait",
        "vendor.qblox.acquire",
        "vendor.qblox.set_acquisition_rotation",
        "waveform.iq_drag",
        "measure.fields.iq",
        "measure.fields.state",
    ):
        assert token in caps.capabilities, token
    # Block, expression and sweep tokens describe program structure, not a bus, so they route to
    # the platform slot and have no place in a bus profile.
    for token in ("block.sweep", "expr.constant", "sweep.linear"):
        assert token not in caps.capabilities, f"{token} belongs on the platform profile"
    # Limits: only min_wait_duration_ns lives on the bus side.
    assert caps.limits["min_wait_duration_ns"] > 0
    assert "max_loop_nesting" not in caps.limits


def test_qprogram_base_profile_carries_platform_side_tokens() -> None:
    """``qprogram-base-v1`` holds every non-bus capability the DSL has: blocks, sweeps, expressions."""
    caps = CompilerCapabilities.from_profile("qprogram-base-v1")
    for token in (
        "block.sweep",
        "block.parallel",
        "block.conditional",
        "sweep.linear",
        "sweep.arbitrary",
        "expr.constant",
        "expr.measurement_ref",
    ):
        assert token in caps.capabilities, token
    # Every core op touches a bus, ``set_parameter`` and ``get_parameter`` included, so op tokens are
    # a bus-profile concern.
    for token in ("op.set_parameter", "op.get_parameter"):
        assert token not in caps.capabilities, f"{token} belongs on a bus profile"
    # measure.fields.* travels with Measure to the bus.
    for token in ("measure.fields.iq", "measure.fields.state"):
        assert token not in caps.capabilities, f"{token} belongs on a bus profile"


def test_qblox_default_vendor_versions_record_qblox() -> None:
    caps = CompilerCapabilities.from_profile("qblox-default-v1")
    assert "qblox" in caps.vendor_versions


# ---------------------------------------------------------------------------
# Happy path: every supported op validates clean
# ---------------------------------------------------------------------------


def test_full_program_with_every_supported_construct_validates_clean() -> None:
    caps = _make_caps()
    p = QProgram()
    freq = p.variable("freq")
    pi_wf = IQDrag(amplitude=0.5, duration=40, sigma=8, beta=0.1)
    readout_wf = IQPair(I=Square(0.5, 200), Q=Square(0.0, 200))
    weights = IQPair(I=Square(1.0, 200), Q=Square(1.0, 200))
    with p.average(1000), p.sweep(freq, Range(5e9, 6e9, 1e6)):
        p.set_frequency("drive_q0", freq)
        p.play("drive_q0", pi_wf)
        p.sync()
        p.measure("readout_q0", readout_wf, weights)
    diagnostics = _diagnostics(p, caps)
    assert diagnostics == [], diagnostics


def test_qblox_vendor_op_validates_clean() -> None:
    caps = _make_caps()
    p = qprogram_qblox.QProgram()
    weights = IQPair(I=Square(1.0, 200), Q=Square(1.0, 200))
    p.qblox.acquire("readout_q0", weights)
    assert _diagnostics(p, caps) == []


def test_every_vendor_op_in_the_profile_validates_clean() -> None:
    """One program touching all six ``vendor.qblox.*`` tokens the profile lists."""
    caps = _make_caps()
    p = qprogram_qblox.QProgram()
    p.qblox.set_markers("drive_q0", "0001")
    p.qblox.set_trigger("drive_q0", duration=100, outputs=[1, 2], position="end")
    p.qblox.wait_trigger("drive_q0", duration=1000, port=1)
    p.qblox.set_acquisition_rotation("readout_q0", math.pi / 4)
    p.qblox.set_acquisition_threshold("readout_q0", 0.42)
    p.qblox.acquire("readout_q0", IQPair(I=Square(1.0, 200), Q=Square(1.0, 200)))
    diagnostics = _diagnostics(p, caps)
    assert diagnostics == [], diagnostics


# ---------------------------------------------------------------------------
# Predicate: arbitrary-wait-sweep (hard Diagnostic)
# ---------------------------------------------------------------------------


def test_arbitrary_sweep_at_wait_duration_is_rejected() -> None:
    caps = _make_caps()
    p = QProgram()
    d = p.variable("dur")
    with p.sweep(d, Values(np.array([100, 200, 400]))):
        p.wait("drive_q0", d)
    diagnostics = _diagnostics(p, caps)
    codes = [diag.code for diag in diagnostics]
    assert "qblox.arbitrary-wait-sweep" in codes


def test_linear_sweep_at_wait_duration_is_accepted() -> None:
    caps = _make_caps()
    p = QProgram()
    d = p.variable("dur")
    with p.sweep(d, Range(100, 500, 100)):
        p.wait("drive_q0", d)
    diagnostics = _diagnostics(p, caps)
    assert "qblox.arbitrary-wait-sweep" not in [diag.code for diag in diagnostics]


# ---------------------------------------------------------------------------
# Predicate: IQDrag-sigma sweep, DomainConstraint(exclude=rt), forced-host warning
# ---------------------------------------------------------------------------


def test_iq_drag_sigma_sweep_forces_host() -> None:
    """The DomainConstraint excludes rt, so the binding loop classifies as ``{host}`` alone and a
    single ``forced-host`` warning surfaces on the topmost forced block.
    """
    caps = _make_caps()
    p = QProgram()
    sigma = p.variable("sigma")
    with p.average(100), p.sweep(sigma, Range(1.0, 10.0, 1.0)):
        p.play("drive_q0", IQDrag(amplitude=0.5, duration=40, sigma=sigma, beta=0.1))
    diagnostics, plan = validate(p, caps)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert errors == [], errors
    forced = [d for d in diagnostics if d.code == "forced-host"]
    assert len(forced) == 1, forced
    assert forced[0].severity == "warning"
    # The topmost forced block is the Average, whose parent is the root body.
    assert isinstance(forced[0].node, Average)
    sweep_block = next(n for n in p.body.walk() if isinstance(n, Sweep))
    assert plan[sweep_block] == frozenset({"host"})


def test_iq_drag_amplitude_sweep_stays_rt() -> None:
    """Sweeping IQDrag.amplitude instead of sigma leaves the constraint quiet and rt in the plan."""
    caps = _make_caps()
    p = QProgram()
    amp = p.variable("amp")
    with p.sweep(amp, Range(0.0, 1.0, 0.1)):
        p.play("drive_q0", IQDrag(amplitude=amp, duration=40, sigma=8, beta=0.1))
    diagnostics, plan = validate(p, caps)
    forced = [d for d in diagnostics if d.code == "forced-host"]
    assert forced == []
    sweep_block = next(n for n in p.body.walk() if isinstance(n, Sweep))
    assert "rt" in plan[sweep_block]


def test_iq_drag_sigma_without_a_binding_loop_stays_rt() -> None:
    """A ``sigma`` variable no loop binds is a constant at upload time, so nothing is excluded."""
    caps = _make_caps()
    p = QProgram()
    sigma = p.variable("sigma")
    p.play("drive_q0", IQDrag(amplitude=0.5, duration=40, sigma=sigma, beta=0.1))
    diagnostics, plan = validate(p, caps)
    assert diagnostics == [], diagnostics
    play = next(n for n in p.body.walk() if isinstance(n, Play))
    assert plan[play] == frozenset({"rt"})


# ---------------------------------------------------------------------------
# Limits sourced from the profile
# ---------------------------------------------------------------------------


def test_min_wait_duration_limit_fires() -> None:
    caps = _make_caps()
    # qblox-default-v1 sets min_wait_duration_ns=4, so a 2 ns wait is out of range.
    p = QProgram()
    p.wait("drive_q0", 2)
    diagnostics = _diagnostics(p, caps)
    assert any(
        diag.code == "limit-exceeded" and diag.limit and diag.limit[0] == "min_wait_duration_ns" for diag in diagnostics
    )


def test_device_can_tighten_limits_via_platform_overrides() -> None:
    """``max_loop_nesting`` is counted at the platform slot, so an override goes there."""
    caps = _make_caps(platform_limit_overrides={"max_loop_nesting": 1})
    p = QProgram()
    v1 = p.variable("a")
    v2 = p.variable("b")
    with p.sweep(v1, Range(0, 1, 0.1)), p.sweep(v2, Range(0, 1, 0.1)):
        p.play("drive_q0", IQDrag(amplitude=0.5, duration=40, sigma=8, beta=0.1))
    diagnostics = _diagnostics(p, caps)
    assert any(
        diag.code == "limit-exceeded" and diag.limit and diag.limit[0] == "max_loop_nesting" for diag in diagnostics
    )


# ---------------------------------------------------------------------------
# Conditional execution
# ---------------------------------------------------------------------------


def test_conditional_active_reset_validates_clean() -> None:
    """The canonical motivation: portable active reset expressed as a conditional."""
    caps = _make_caps()
    p = QProgram()
    m = p.measure(
        "readout_q0",
        IQPair(I=Square(0.5, 200), Q=Square(0.0, 200)),
        IQPair(I=Square(1.0, 200), Q=Square(1.0, 200)),
        fields=("iq", "state"),
    )
    with p.if_(m.state == 1):
        p.play("drive_q0", "pi_pulse")
    assert _diagnostics(p, caps) == []


def test_conditional_with_full_chain_validates_clean() -> None:
    caps = _make_caps()
    p = QProgram()
    m = p.measure(
        "readout_q0",
        IQPair(I=Square(0.5, 200), Q=Square(0.0, 200)),
        IQPair(I=Square(1.0, 200), Q=Square(1.0, 200)),
        fields=("iq", "state"),
    )
    with p.if_(m.state == 0):
        p.play("drive_q0", "id_pulse")
    with p.elif_(m.state == 1):
        p.play("drive_q0", "pi_pulse")
    with p.else_():
        p.sync()
    assert _diagnostics(p, caps) == []


def test_conditional_missing_state_classification_caught_by_validator() -> None:
    caps = _make_caps()
    p = QProgram()
    m = p.measure(
        "readout_q0",
        IQPair(I=Square(0.5, 200), Q=Square(0.0, 200)),
        IQPair(I=Square(1.0, 200), Q=Square(1.0, 200)),
    )  # default fields=("iq",), so no state to branch on
    with p.if_(m.state == 1):
        p.play("drive_q0", "pi_pulse")
    diagnostics = _diagnostics(p, caps)
    assert any(d.code == "missing-classification" for d in diagnostics)
