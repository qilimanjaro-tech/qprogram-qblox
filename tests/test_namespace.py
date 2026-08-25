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
"""Tests for :class:`~qprogram_qblox.QbloxNamespace`, the typed methods users call.

Each method builds one operation node and appends it to the program's active block. What these
tests pin down is the call surface: defaults, keyword handling, the measurement name counter the
namespace shares with core ``measure``, and the namespace object's lifetime on the program.
"""

from __future__ import annotations

import math

import pytest
from qprogram import MeasurementHandle, Variable
from qprogram.vendor import VendorNamespace

from qprogram_qblox import QProgram as QbloxQProgram
from qprogram_qblox.namespace import QbloxNamespace
from qprogram_qblox.operations import (
    Acquire,
    SetAcquisitionRotation,
    SetAcquisitionThreshold,
    SetMarkers,
    SetTrigger,
    WaitTrigger,
)

# ---------------------------------------------------------------------------
# acquire
# ---------------------------------------------------------------------------


def test_acquire_returns_handle_and_appends_op(qblox_program):
    handle = qblox_program.qblox.acquire("readout", "weights")
    assert isinstance(handle, MeasurementHandle)
    assert len(qblox_program.body.elements) == 1
    assert isinstance(qblox_program.body.elements[0], Acquire)


def test_acquire_uses_per_bus_naming(qblox_program, transmon_schema):
    h0 = qblox_program.qblox.acquire(transmon_schema.q[0].readout, "weights")
    h1 = qblox_program.qblox.acquire(transmon_schema.q[0].readout, "weights")
    assert h0.name == "q0/readout/m0"
    assert h1.name == "q0/readout/m1"


def test_acquire_with_explicit_name(qblox_program):
    h = qblox_program.qblox.acquire("readout", "weights", name="custom")
    assert h.name == "custom"


def test_acquire_with_fields_tuple(qblox_program):
    qblox_program.qblox.acquire("readout", "weights", fields=("iq", "raw"))
    op = qblox_program.body.elements[0]
    assert op.fields == ("iq", "raw")


def test_acquire_with_fields_iterable(qblox_program):
    qblox_program.qblox.acquire("readout", "weights", fields=("raw",))
    op = qblox_program.body.elements[0]
    assert op.fields == ("raw",)


def test_acquire_shares_counter_with_core_measure(qblox_program, transmon_schema):
    """measure + acquire on the same bus share the m0, m1, ... counter."""
    h0 = qblox_program.measure(transmon_schema.q[0].readout, "wf", "weights")
    h1 = qblox_program.qblox.acquire(transmon_schema.q[0].readout, "weights")
    assert h0.name == "q0/readout/m0"
    assert h1.name == "q0/readout/m1"


# ---------------------------------------------------------------------------
# set_markers
# ---------------------------------------------------------------------------


def test_set_markers_appends_op(qblox_program):
    qblox_program.qblox.set_markers("drive", "0001")
    op = qblox_program.body.elements[0]
    assert isinstance(op, SetMarkers)
    assert op.bus == "drive"
    assert op.mask == "0001"


def test_set_markers_returns_none(qblox_program):
    assert qblox_program.qblox.set_markers("drive", "0001") is None


# ---------------------------------------------------------------------------
# set_trigger
# ---------------------------------------------------------------------------


def test_set_trigger_defaults(qblox_program):
    qblox_program.qblox.set_trigger("drive", duration=100)
    op = qblox_program.body.elements[0]
    assert isinstance(op, SetTrigger)
    assert op.duration == 100
    assert op.outputs is None
    assert op.position == "start"


def test_set_trigger_with_all_kwargs(qblox_program):
    qblox_program.qblox.set_trigger("drive", duration=50, outputs=[1, 2], position="end")
    op = qblox_program.body.elements[0]
    assert op.outputs == [1, 2]
    assert op.position == "end"


# ---------------------------------------------------------------------------
# wait_trigger
# ---------------------------------------------------------------------------


def test_wait_trigger_appends_op(qblox_program):
    qblox_program.qblox.wait_trigger("drive", duration=1000, port=2)
    op = qblox_program.body.elements[0]
    assert isinstance(op, WaitTrigger)
    assert op.duration == 1000
    assert op.port == 2


def test_wait_trigger_default_port(qblox_program):
    qblox_program.qblox.wait_trigger("drive", duration=500)
    op = qblox_program.body.elements[0]
    assert op.port is None


# ---------------------------------------------------------------------------
# set_acquisition_threshold
# ---------------------------------------------------------------------------


def test_set_acquisition_threshold_with_float(qblox_program):
    qblox_program.qblox.set_acquisition_threshold("readout", 0.42)
    op = qblox_program.body.elements[0]
    assert isinstance(op, SetAcquisitionThreshold)
    assert op.value == pytest.approx(0.42)


def test_set_acquisition_threshold_with_expression(qblox_program):
    v = Variable("threshold")
    qblox_program.qblox.set_acquisition_threshold("readout", v)
    op = qblox_program.body.elements[0]
    assert op.value is v


# ---------------------------------------------------------------------------
# set_acquisition_rotation
# ---------------------------------------------------------------------------


def test_set_acquisition_rotation_with_float(qblox_program):
    qblox_program.qblox.set_acquisition_rotation("readout", math.pi / 4)
    op = qblox_program.body.elements[0]
    assert isinstance(op, SetAcquisitionRotation)
    assert op.angle == pytest.approx(math.pi / 4)


def test_set_acquisition_rotation_with_expression(qblox_program):
    v = Variable("theta")
    qblox_program.qblox.set_acquisition_rotation("readout", v)
    op = qblox_program.body.elements[0]
    assert op.angle is v


def test_set_acquisition_rotation_and_threshold_coexist(qblox_program):
    """The usual calibrated pairing: rotate, then threshold."""
    qblox_program.qblox.set_acquisition_rotation("readout", math.pi / 4)
    qblox_program.qblox.set_acquisition_threshold("readout", 0.42)
    rot, thr = qblox_program.body.elements
    assert isinstance(rot, SetAcquisitionRotation)
    assert isinstance(thr, SetAcquisitionThreshold)


# ---------------------------------------------------------------------------
# Bus validation in namespace
# ---------------------------------------------------------------------------


def test_acquire_accepts_schema_readout_bus(qblox_program, transmon_schema):
    """A schema readout bus carries an ADC (``acquires=True``), so an acquisition on it is fine."""
    h = qblox_program.qblox.acquire(transmon_schema.q[0].readout, "weights")
    assert isinstance(h, MeasurementHandle)


def test_acquire_accepts_plain_string_bus(qblox_program):
    """Plain string buses opt out of validation."""
    h = qblox_program.qblox.acquire("any_bus", "weights")
    assert isinstance(h, MeasurementHandle)


# ---------------------------------------------------------------------------
# Namespace identity
# ---------------------------------------------------------------------------


def test_namespace_is_subclass_of_vendor_namespace():
    assert issubclass(QbloxNamespace, VendorNamespace)


def test_namespace_holds_program_reference(qblox_program):
    ns = qblox_program.qblox
    assert ns._program is qblox_program  # type: ignore[attr-defined]


def test_namespace_cached_per_instance(qblox_program):
    """Same namespace instance returned on repeated access."""
    assert qblox_program.qblox is qblox_program.qblox


def test_namespace_distinct_per_program():
    p1 = QbloxQProgram()
    p2 = QbloxQProgram()
    assert p1.qblox is not p2.qblox


def test_namespace_appends_to_program_without_mixin(base_program, transmon_schema):
    """The dynamically resolved namespace appends to the body just as the typed property does."""
    base_program.qblox.set_markers(transmon_schema.q[0].drive, "0001")  # type: ignore[attr-defined]
    op = base_program.body.elements[0]
    assert isinstance(op, SetMarkers)
    assert op.bus == transmon_schema.q[0].drive
