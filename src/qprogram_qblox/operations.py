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
"""Qblox-specific Operation classes.

Each class is a concrete :class:`~qprogram.operations.Operation` subclass that lives in the QProgram
AST. They are the data nodes: typed attributes plus the capability tokens they require, serialized
to and from ``.qp`` by the vendor registry.

They span both kinds of vendor operation. :class:`Acquire`, :class:`SetMarkers`,
:class:`SetTrigger` and :class:`WaitTrigger` each map to one sequencer instruction;
:class:`SetAcquisitionThreshold` and :class:`SetAcquisitionRotation` map to no sequencer instruction
at all and are realized as slow-control parameter writes. The AST draws no distinction between the
two, and neither does the ``.qp`` format.

A class declares :attr:`~qprogram.operations.Operation.BUS_ATTRS` and
:attr:`~qprogram.operations.Operation.WAVEFORM_ATTRS` only where its data shape differs from the
``Operation`` defaults. The base class's introspection methods (``variables``, ``buses``,
``waveforms``, ``walk``) read those declarations, so no subclass here overrides them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from qprogram.operations.operation import MeasurementField, MeasurementOperation, Operation, normalize_fields

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qprogram.result import MeasurementHandle
    from qprogram.variable import Expression
    from qprogram.waveforms.waveform import IQWaveform


class Acquire(MeasurementOperation):
    """An acquisition on a readout bus, with no readout pulse of its own.

    Where core ``measure`` plays a readout pulse and integrates the response, ``acquire`` only
    integrates, which is what a program wants when the pulse is driven separately. It is a
    :class:`~qprogram.operations.operation.MeasurementOperation` like ``measure``, so it takes part
    in the program's per-bus measurement-name counter: an ``acquire`` after a ``measure`` on the same
    qubit picks up the next free name on that qubit.

    Args:
        bus (str): Readout bus to acquire on.
        weights (IQWaveform | str): Integration weights, either a concrete
            :class:`~qprogram.waveforms.IQWaveform` or a string alias resolved later by
            :meth:`~qprogram.QProgram.with_waveforms`.
        handle (MeasurementHandle): The canonical :class:`~qprogram.MeasurementHandle` for this
            acquisition. See :class:`~qprogram.operations.Measure` for what the runtime writes onto
            it and who reads it.
        fields (Iterable[MeasurementField]): Which measurement fields the platform produces, as an
            iterable of :class:`~qprogram.MeasurementField` members. Default
            ``(MeasurementField.IQ,)``. See :class:`~qprogram.operations.Measure` for the full
            description. Stored canonically ordered and deduplicated by
            :func:`~qprogram.operations.operation.normalize_fields`.

    Raises:
        ValidationError: If ``fields`` is a bare string, is not iterable, requests no field at all,
            or names a field that is not registered.
    """

    WAVEFORM_ATTRS: ClassVar[tuple[str, ...]] = ("weights",)

    def __init__(
        self,
        bus: str,
        weights: IQWaveform | str,
        handle: MeasurementHandle,
        fields: Iterable[MeasurementField] = (MeasurementField.IQ,),
    ) -> None:
        self.bus = bus
        self.weights = weights
        self.handle = handle
        self.fields: tuple[str, ...] = normalize_fields(fields)

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qblox.acquire`` plus the weights and requested-field tokens.

        ``waveform.iq`` is always required, since an acquisition integrates an IQ pair. String
        weights contribute ``waveform.alias``; concrete weights contribute the per-class token from
        :func:`qprogram.protocol.waveform_token` when their class is registered. The
        ``measure.fields.<name>`` tokens come from
        :meth:`~qprogram.operations.operation.MeasurementOperation.required_capabilities`.
        """
        from qprogram.protocol import waveform_token  # ruff: ignore[import-outside-top-level]

        caps = super().required_capabilities() | {"vendor.qblox.acquire", "waveform.iq"}
        if isinstance(self.weights, str):
            caps.add("waveform.alias")
        else:
            tok = waveform_token(self.weights)
            if tok is not None:
                caps.add(tok)
        return caps


class SetMarkers(Operation):
    """A new 4-bit marker output mask on a qblox sequencer.

    Args:
        bus (str): Bus whose marker outputs to drive.
        mask (str): Four characters of ``0`` and ``1``, one per marker line. ``"0001"`` enables
            marker 1.
    """

    def __init__(self, bus: str, mask: str) -> None:
        self.bus = bus
        self.mask = mask

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qblox.set_markers``, the operation's identity token."""
        return {"vendor.qblox.set_markers"}


class SetTrigger(Operation):
    """A trigger output configuration on a qblox sequencer.

    Args:
        bus (str): Bus whose trigger outputs to arm.
        duration (int): Trigger-active duration in nanoseconds.
        outputs (list[int] | int | None): Trigger output indices to arm, one index or a list of
            them. ``None`` leaves the selection to the platform.
        position (str): Point in the operation at which the trigger fires, either ``"start"`` or
            ``"end"``. Default ``"start"``.
    """

    def __init__(
        self,
        bus: str,
        duration: int,
        outputs: list[int] | int | None = None,
        position: str = "start",
    ) -> None:
        self.bus = bus
        self.duration = duration
        self.outputs = outputs
        self.position = position

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qblox.set_trigger``, the operation's identity token."""
        return {"vendor.qblox.set_trigger"}


class WaitTrigger(Operation):
    """A wait for an external trigger on a qblox sequencer.

    Args:
        bus (str): Bus whose sequencer waits.
        duration (int): Timeout in nanoseconds, after which the sequencer stops waiting.
        port (int | None): Trigger input port to listen on. ``None`` leaves the choice to the
            platform.
    """

    def __init__(self, bus: str, duration: int, port: int | None = None) -> None:
        self.bus = bus
        self.duration = duration
        self.port = port

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qblox.wait_trigger``, the operation's identity token."""
        return {"vendor.qblox.wait_trigger"}


class SetAcquisitionThreshold(Operation):
    """A new qubit-state discrimination threshold on a readout bus.

    A **host-side-only** vendor operation: the qblox platform realizes it as a slow-control
    parameter write at execution time and emits no sequencer instruction. Vendor operations do not
    have to map onto sequencer instructions at all: an extension may expose any operation whose
    execution its platform knows how to interpret, be that a sequencer command, a parameter write,
    or a multi-step orchestration.

    Args:
        bus (str): Readout bus whose discrimination threshold to set.
        value (float | Expression): Threshold, in volts after integration. Accepts an
            :class:`~qprogram.Expression` for sweeps.
    """

    def __init__(self, bus: str, value: float | Expression) -> None:
        self.bus = bus
        self.value = value

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qblox.set_acquisition_threshold`` plus the ``value`` expression tokens."""
        from qprogram.protocol import expression_tokens  # ruff: ignore[import-outside-top-level]

        return {"vendor.qblox.set_acquisition_threshold"} | expression_tokens(self.value)


class SetAcquisitionRotation(Operation):
    """A new acquisition rotation angle on a readout bus.

    The other half of qblox's thresholded acquisition, and the sibling of
    :class:`SetAcquisitionThreshold`: the integrated IQ point is rotated by this angle so that the
    ground and excited populations separate along a single axis, and only then compared against the
    threshold. Setting one without the other is legal, since they are independent parameters, but a
    calibrated discrimination usually writes both.

    Host-side-only like the threshold: a slow-control parameter write at execution time, not a
    sequencer instruction.

    Args:
        bus (str): Readout bus whose acquisition rotation to set.
        angle (float | Expression): Rotation angle in **radians**, the unit convention of the core
            phase operations (:class:`~qprogram.operations.SetPhase`). Accepts an
            :class:`~qprogram.Expression` for sweeps, which is the usual way to calibrate it. Values
            outside ``[0, 2π)`` are the platform's to normalize or reject, not this node's: a swept
            angle has no literal value to check at build time.
    """

    def __init__(self, bus: str, angle: float | Expression) -> None:
        self.bus = bus
        self.angle = angle

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qblox.set_acquisition_rotation`` plus the ``angle`` expression tokens."""
        from qprogram.protocol import expression_tokens  # ruff: ignore[import-outside-top-level]

        return {"vendor.qblox.set_acquisition_rotation"} | expression_tokens(self.angle)
