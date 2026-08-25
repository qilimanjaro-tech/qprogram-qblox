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
"""Tests for the qblox operation classes, the data nodes that live in the AST.

Construction, the introspection contract every :class:`~qprogram.operations.Operation` owes the
walker (``buses``, ``waveforms``, ``variables``), structural equality, and the capability tokens
each node declares for itself.
"""

from __future__ import annotations

import math

import pytest
from qprogram import MeasurementField, MeasurementHandle, ValidationError, Variable
from qprogram.waveforms import IQPair, Square

from qprogram_qblox.operations import (
    Acquire,
    SetAcquisitionRotation,
    SetAcquisitionThreshold,
    SetMarkers,
    SetTrigger,
    WaitTrigger,
)

# ---------------------------------------------------------------------------
# Acquire
# ---------------------------------------------------------------------------


def test_acquire_construct_defaults():
    op = Acquire("readout", "weights", handle=MeasurementHandle("q0_m0"))
    assert op.bus == "readout"
    assert op.weights == "weights"
    assert op.name == "q0_m0"
    assert op.fields == ("iq",)


def test_acquire_fields_normalized_from_iterable():
    op = Acquire("readout", "weights", handle=MeasurementHandle("m0"), fields=["iq", "raw"])
    assert op.fields == ("iq", "raw")


def test_acquire_fields_accept_enum_members_and_canonicalize():
    op = Acquire(
        "readout",
        "weights",
        handle=MeasurementHandle("m0"),
        fields=(MeasurementField.RAW, MeasurementField.STATE),
    )
    assert op.fields == ("state", "raw")


def test_acquire_fields_rejects_bare_csv_string():
    """The vendor op inherits core's rejection of a bare string: there is no comma-joined spelling."""
    with pytest.raises(ValidationError, match="not the bare string"):
        Acquire("readout", "weights", handle=MeasurementHandle("m0"), fields="iq,raw")


def test_acquire_fields_rejects_unknown_field():
    with pytest.raises(ValidationError, match="unknown measurement field"):
        Acquire("readout", "weights", handle=MeasurementHandle("m0"), fields=("iqq",))


def test_acquire_introspection():
    op = Acquire("bus", "weights", handle=MeasurementHandle("m0"))
    assert list(op.buses()) == ["bus"]
    assert list(op.waveforms()) == ["weights"]
    assert list(op.variables()) == []


def test_acquire_with_inline_waveform():
    wf = IQPair(Square(1.0, 100), Square(1.0, 100))
    op = Acquire("bus", wf, handle=MeasurementHandle("m0"))
    assert op.weights is wf
    assert list(op.waveforms()) == [wf]


def test_acquire_structural_equality():
    a = Acquire("bus", "w", handle=MeasurementHandle("m0"), fields=("iq",))
    b = Acquire("bus", "w", handle=MeasurementHandle("m0"), fields=("iq",))
    assert a == b
    assert hash(a) == hash(b)


def test_acquire_distinct_when_different():
    a = Acquire("bus", "w", handle=MeasurementHandle("m0"))
    b = Acquire("bus", "w", handle=MeasurementHandle("m1"))
    assert a != b


def test_acquire_required_capabilities_with_weights_alias():
    """A named weights alias asks the platform for ``waveform.alias``, not a waveform class."""
    op = Acquire("readout", "weights", handle=MeasurementHandle("m0"))
    assert op.required_capabilities() == {
        "vendor.qblox.acquire",
        "waveform.iq",
        "waveform.alias",
        "measure.fields.iq",
    }


def test_acquire_required_capabilities_with_inline_weights():
    """Inline weights add their own class token, and each requested field adds one too."""
    weights = IQPair(Square(1.0, 200), Square(1.0, 200))
    op = Acquire("readout", weights, handle=MeasurementHandle("m0"), fields=("iq", "state"))
    assert op.required_capabilities() == {
        "vendor.qblox.acquire",
        "waveform.iq",
        "waveform.iq_pair",
        "measure.fields.iq",
        "measure.fields.state",
    }


def test_acquire_required_capabilities_unregistered_weights_class():
    """Weights whose class carries no registered token contribute only the channel-kind token."""

    class _Fake(IQPair):
        pass

    op = Acquire("readout", _Fake(Square(1.0, 200), Square(1.0, 200)), handle=MeasurementHandle("m0"))
    assert op.required_capabilities() == {
        "vendor.qblox.acquire",
        "waveform.iq",
        "measure.fields.iq",
    }


# ---------------------------------------------------------------------------
# SetMarkers
# ---------------------------------------------------------------------------


def test_set_markers_construct():
    op = SetMarkers("drive", "0001")
    assert op.bus == "drive"
    assert op.mask == "0001"


@pytest.mark.parametrize("mask", ["0000", "1111", "1010", "0001"])
def test_set_markers_various_masks(mask):
    op = SetMarkers("bus", mask)
    assert op.mask == mask


def test_set_markers_introspection():
    op = SetMarkers("bus", "0001")
    assert list(op.buses()) == ["bus"]
    assert list(op.waveforms()) == []
    assert list(op.variables()) == []


def test_set_markers_equality():
    assert SetMarkers("bus", "0001") == SetMarkers("bus", "0001")
    assert SetMarkers("bus", "0001") != SetMarkers("bus", "0010")


def test_set_markers_required_capabilities():
    assert SetMarkers("bus", "0001").required_capabilities() == {"vendor.qblox.set_markers"}


# ---------------------------------------------------------------------------
# SetTrigger
# ---------------------------------------------------------------------------


def test_set_trigger_defaults():
    op = SetTrigger("bus", duration=100)
    assert op.bus == "bus"
    assert op.duration == 100
    assert op.outputs is None
    assert op.position == "start"


def test_set_trigger_with_outputs_list():
    op = SetTrigger("bus", duration=50, outputs=[1, 2, 3])
    assert op.outputs == [1, 2, 3]


def test_set_trigger_with_outputs_int():
    op = SetTrigger("bus", duration=50, outputs=2)
    assert op.outputs == 2


def test_set_trigger_with_position_end():
    op = SetTrigger("bus", duration=50, position="end")
    assert op.position == "end"


def test_set_trigger_equality():
    a = SetTrigger("bus", 100, outputs=[1, 2], position="end")
    b = SetTrigger("bus", 100, outputs=[1, 2], position="end")
    assert a == b


def test_set_trigger_required_capabilities():
    """The payload is fixed data, so the token set never varies with the arguments."""
    plain = SetTrigger("bus", duration=100)
    configured = SetTrigger("bus", duration=100, outputs=[1, 2], position="end")
    assert plain.required_capabilities() == {"vendor.qblox.set_trigger"}
    assert configured.required_capabilities() == plain.required_capabilities()


# ---------------------------------------------------------------------------
# WaitTrigger
# ---------------------------------------------------------------------------


def test_wait_trigger_defaults():
    op = WaitTrigger("bus", duration=1000)
    assert op.bus == "bus"
    assert op.duration == 1000
    assert op.port is None


def test_wait_trigger_with_port():
    op = WaitTrigger("bus", duration=500, port=3)
    assert op.port == 3


def test_wait_trigger_required_capabilities():
    assert WaitTrigger("bus", duration=500).required_capabilities() == {"vendor.qblox.wait_trigger"}


# ---------------------------------------------------------------------------
# SetAcquisitionThreshold
# ---------------------------------------------------------------------------


def test_set_acquisition_threshold_float():
    op = SetAcquisitionThreshold("readout", value=0.42)
    assert op.bus == "readout"
    assert op.value == pytest.approx(0.42)


def test_set_acquisition_threshold_with_expression():
    v = Variable("threshold")
    op = SetAcquisitionThreshold("readout", value=v)
    assert op.value is v
    assert list(op.variables()) == [v]


def test_set_acquisition_threshold_no_waveforms():
    op = SetAcquisitionThreshold("readout", 0.5)
    assert list(op.buses()) == ["readout"]
    assert list(op.waveforms()) == []


def test_set_acquisition_threshold_required_capabilities():
    op = SetAcquisitionThreshold("readout", 0.42)
    assert op.required_capabilities() == {"vendor.qblox.set_acquisition_threshold"}


def test_set_acquisition_threshold_swept_value_adds_expression_token():
    op = SetAcquisitionThreshold("readout", Variable("threshold"))
    assert op.required_capabilities() == {
        "vendor.qblox.set_acquisition_threshold",
        "expr.variable",
    }


# ---------------------------------------------------------------------------
# SetAcquisitionRotation
# ---------------------------------------------------------------------------


def test_set_acquisition_rotation_float():
    op = SetAcquisitionRotation("readout", angle=math.pi / 4)
    assert op.bus == "readout"
    assert op.angle == pytest.approx(math.pi / 4)


def test_set_acquisition_rotation_with_expression():
    v = Variable("theta")
    op = SetAcquisitionRotation("readout", angle=v)
    assert op.angle is v
    assert list(op.variables()) == [v]


def test_set_acquisition_rotation_no_waveforms():
    op = SetAcquisitionRotation("readout", math.pi / 2)
    assert list(op.buses()) == ["readout"]
    assert list(op.waveforms()) == []


def test_set_acquisition_rotation_required_capabilities():
    op = SetAcquisitionRotation("readout", math.pi / 4)
    assert op.required_capabilities() == {"vendor.qblox.set_acquisition_rotation"}


def test_set_acquisition_rotation_swept_angle_adds_expression_token():
    op = SetAcquisitionRotation("readout", Variable("theta"))
    assert op.required_capabilities() == {
        "vendor.qblox.set_acquisition_rotation",
        "expr.variable",
    }


def test_set_acquisition_rotation_is_independent_of_threshold():
    """Sibling ops with distinct nodes and distinct tokens: neither implies the other."""
    rot = SetAcquisitionRotation("readout", math.pi / 4)
    thr = SetAcquisitionThreshold("readout", math.pi / 4)  # same payload on purpose
    assert rot != thr
    assert rot.required_capabilities() != thr.required_capabilities()


def test_set_acquisition_rotation_equality():
    a = SetAcquisitionRotation("readout", math.pi / 4)
    b = SetAcquisitionRotation("readout", math.pi / 4)
    assert a == b
    assert hash(a) == hash(b)
