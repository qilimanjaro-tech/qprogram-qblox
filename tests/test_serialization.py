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
"""Tests for the ``.qp`` text form of the qblox vendor operations.

Every operation the package registers has to survive ``dumps`` then ``loads`` unchanged, and a
file that carries any of them has to declare ``require qblox <major.minor>`` so the parser can
check the installed extension before it reads the body.
"""

from __future__ import annotations

import math

import pytest
from qprogram import ParseError, dumps, loads
from qprogram.sweeps import Range
from qprogram.waveforms import IQDrag, IQPair, Square

from qprogram_qblox import QProgram as QbloxQProgram
from qprogram_qblox.operations import (
    Acquire,
    SetAcquisitionRotation,
    SetAcquisitionThreshold,
    SetMarkers,
    SetTrigger,
    WaitTrigger,
)

# ---------------------------------------------------------------------------
# Vendor-require header
# ---------------------------------------------------------------------------


def test_dumps_includes_require_qblox():
    p = QbloxQProgram()
    p.qblox.set_markers("drive", "0001")
    text = dumps(p)
    assert "require qblox" in text


def test_dumps_no_require_when_no_qblox_ops():
    p = QbloxQProgram()
    p.wait("bus", 100)
    text = dumps(p)
    assert "require qblox" not in text


# ---------------------------------------------------------------------------
# Per-operation round-trips
# ---------------------------------------------------------------------------


def test_acquire_round_trip(qblox_program, transmon_schema):
    qblox_program.qblox.acquire(transmon_schema.q[0].readout, "weights")
    text = dumps(qblox_program)
    assert "qblox.acquire" in text
    reloaded = loads(text)
    assert dumps(reloaded) == text


def test_acquire_with_fields_round_trip(qblox_program, transmon_schema):
    qblox_program.qblox.acquire(transmon_schema.q[0].readout, "weights", fields=("iq", "raw"))
    text = dumps(qblox_program)
    assert 'fields=["iq", "raw"]' in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, Acquire)
    assert op.fields == ("iq", "raw")


def test_set_markers_round_trip():
    p = QbloxQProgram()
    p.qblox.set_markers("drive", "0001")
    text = dumps(p)
    assert "qblox.set_markers" in text
    assert '"0001"' in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, SetMarkers)
    assert op.mask == "0001"


def test_set_trigger_round_trip():
    p = QbloxQProgram()
    p.qblox.set_trigger("drive", duration=100, outputs=3, position="end")
    text = dumps(p)
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, SetTrigger)
    assert op.duration == 100
    assert op.outputs == 3
    assert op.position == "end"


def test_set_trigger_round_trip_minimal():
    p = QbloxQProgram()
    p.qblox.set_trigger("drive", duration=50)
    text = dumps(p)
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert op.duration == 50


def test_set_trigger_with_list_outputs_round_trips():
    """A bracket literal survives tokenizing: ``outputs=[1, 2]`` reloads as the same list."""
    p = QbloxQProgram()
    p.qblox.set_trigger("drive", duration=100, outputs=[1, 2])
    text = dumps(p)
    assert "outputs=[1, 2]" in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, SetTrigger)
    assert op.outputs == [1, 2]
    assert reloaded.body == p.body


def test_wait_trigger_round_trip():
    p = QbloxQProgram()
    p.qblox.wait_trigger("drive", duration=1000, port=2)
    text = dumps(p)
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, WaitTrigger)
    assert op.duration == 1000
    assert op.port == 2


def test_set_acquisition_threshold_round_trip():
    p = QbloxQProgram()
    p.qblox.set_acquisition_threshold("readout", 0.42)
    text = dumps(p)
    assert "qblox.set_acquisition_threshold" in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, SetAcquisitionThreshold)
    assert op.value == pytest.approx(0.42)


def test_set_acquisition_threshold_expression_round_trip():
    p = QbloxQProgram()
    v = p.variable("threshold")
    p.qblox.set_acquisition_threshold("readout", v)
    text = dumps(p)
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert op.value.id == v.id  # type: ignore[union-attr]


def test_set_acquisition_rotation_round_trip():
    p = QbloxQProgram()
    p.qblox.set_acquisition_rotation("readout", math.pi / 4)
    text = dumps(p)
    assert "qblox.set_acquisition_rotation" in text
    # The writer emits the float's repr, so no precision is lost on the way out.
    assert repr(math.pi / 4) in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, SetAcquisitionRotation)
    assert op.angle == pytest.approx(math.pi / 4)


def test_set_acquisition_rotation_expression_round_trip():
    p = QbloxQProgram()
    v = p.variable("theta")
    p.qblox.set_acquisition_rotation("readout", v)
    text = dumps(p)
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert op.angle.id == v.id  # type: ignore[union-attr]


def test_acquire_emits_name_kwarg():
    """Measurement names travel as ``name="..."``, matching core measure's wire form."""
    p = QbloxQProgram()
    p.qblox.acquire("readout", "weights")
    text = dumps(p)
    assert 'qblox.acquire "readout" "weights" name="m0"' in text
    reloaded = loads(text)
    op = reloaded.body.elements[0]
    assert isinstance(op, Acquire)
    assert op.name == "m0"


# ---------------------------------------------------------------------------
# Inline waveforms inside vendor ops
# ---------------------------------------------------------------------------


def test_acquire_with_inline_iq_waveform_round_trip():
    p = QbloxQProgram()
    p.qblox.acquire("readout", IQPair(Square(1.0, 100), Square(1.0, 100)), name="m0")
    text = dumps(p)
    reloaded = loads(text)
    assert dumps(reloaded) == text


# ---------------------------------------------------------------------------
# Combined with core ops
# ---------------------------------------------------------------------------


def test_round_trip_qblox_and_core_ops(transmon_schema):
    p = QbloxQProgram(schema=transmon_schema)
    p.play(transmon_schema.q[0].drive, "wf")
    p.qblox.set_markers(transmon_schema.q[0].drive, "0001")
    p.qblox.acquire(transmon_schema.q[0].readout, "weights")
    text = dumps(p)
    reloaded = loads(text)
    assert dumps(reloaded) == text


def test_vendor_op_inside_conditional_emits_require():
    """A qblox op reachable only inside an ``if_`` arm is enough to put the ``require`` line in."""
    p = QbloxQProgram()
    h = p.measure("readout", "r", "w", fields=("iq", "state"))
    with p.if_(h.state == 1):
        p.qblox.set_markers("drive", "0001")
    text = dumps(p)
    assert "require qblox" in text
    reloaded = loads(text)
    markers = [n for n in reloaded.body.walk() if isinstance(n, SetMarkers)]
    assert len(markers) == 1


def test_set_acquisition_rotation_swept_in_loop_round_trip(transmon_schema):
    """The calibration shape: sweep the angle, threshold once outside the loop."""
    p = QbloxQProgram(schema=transmon_schema)
    theta = p.variable("theta", units="rad")
    with p.sweep(theta, Range(0.0, 2 * math.pi, math.pi / 36)):  # a full turn in 5 degree steps
        p.qblox.set_acquisition_rotation(transmon_schema.q[0].readout, theta)
        p.qblox.acquire(transmon_schema.q[0].readout, "weights")
    p.qblox.set_acquisition_threshold(transmon_schema.q[0].readout, 0.42)
    text = dumps(p)
    assert dumps(loads(text)) == text


# ---------------------------------------------------------------------------
# Vendor-compatibility check
# ---------------------------------------------------------------------------


def test_loads_with_matching_qblox_require_ok():
    p = QbloxQProgram()
    p.qblox.set_markers("drive", "0001")
    reloaded = loads(dumps(p))
    assert isinstance(reloaded.body.elements[0], SetMarkers)


def test_loads_with_future_minor_rejected():
    """A file asking for a minor the installed extension does not have cannot be parsed."""
    text = '#!QProgram 1.0\nrequire qblox 0.99\nbody:\n  qblox.set_markers "drive" "0001"\n'
    with pytest.raises(ParseError, match="minor version too old"):
        loads(text)


def test_loads_with_wrong_major_rejected():
    """Majors must match exactly: the wire form of an operation may change between them."""
    text = '#!QProgram 1.0\nrequire qblox 999.0\nbody:\n  qblox.set_markers "drive" "0001"\n'
    with pytest.raises(ParseError, match="major versions must match"):
        loads(text)


# ---------------------------------------------------------------------------
# Byte-stability across a feature-rich program
# ---------------------------------------------------------------------------


def test_full_features_round_trip(transmon_schema):
    p = QbloxQProgram(label="big-qblox", schema=transmon_schema)
    v = p.variable("freq")
    with p.average(100), p.sweep(v, Range(4e9, 6e9, 1e6)):
        p.set_frequency(transmon_schema.q[0].drive, v)
        p.qblox.set_markers(transmon_schema.q[0].drive, "0001")
        p.qblox.set_trigger(transmon_schema.q[0].drive, duration=10)
        p.play(transmon_schema.q[0].drive, IQDrag(0.5, 40, 2.5, 0.1))
        p.qblox.wait_trigger(transmon_schema.q[0].drive, duration=100, port=1)
        p.qblox.acquire(transmon_schema.q[0].readout, "weights", fields=("iq", "raw"))
    p.qblox.set_acquisition_threshold(transmon_schema.q[0].readout, 0.5)

    text = dumps(p)
    reloaded = loads(text)
    assert dumps(reloaded) == text
    assert reloaded.body == p.body
