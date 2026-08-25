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
"""Typed :class:`~qprogram.VendorNamespace` for Qblox operations.

Each method on :class:`QbloxNamespace` is a typed wrapper that builds the matching
:class:`~qprogram.operations.Operation` subclass from :mod:`qprogram_qblox.operations` and appends
it to the program's active block. This is where explicit parameter types live, so editors complete
and type-checkers check ``program.qblox.<operation>(...)``. The dynamic ``__getattr__`` on
:class:`~qprogram.QProgram` dispatches the same calls at runtime; the typed namespace is what makes
them discoverable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qprogram.operations.operation import MeasurementField
from qprogram.vendor import VendorNamespace

from qprogram_qblox.operations import (
    Acquire,
    SetAcquisitionRotation,
    SetAcquisitionThreshold,
    SetMarkers,
    SetTrigger,
    WaitTrigger,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qprogram.result import MeasurementHandle
    from qprogram.variable import Expression
    from qprogram.waveforms.waveform import IQWaveform


class QbloxNamespace(VendorNamespace):
    """Qblox vendor namespace, reached as ``program.qblox.<operation>()``.

    Attached to every :class:`~qprogram.QProgram` instance as ``.qblox`` once the
    :mod:`qprogram_qblox` package is imported. Each method validates its arguments through the typed
    signature, constructs the matching operation, and appends it to the program's currently active
    block.
    """

    def acquire(
        self,
        bus: str,
        weights: IQWaveform | str,
        fields: Iterable[MeasurementField] = (MeasurementField.IQ,),
        *,
        name: str | None = None,
    ) -> MeasurementHandle:
        """Append an :class:`~qprogram_qblox.operations.Acquire` operation.

        The handle's name comes from the same per-bus counter core
        :meth:`~qprogram.QProgram.measure` draws on, so two acquisitions on ``q[0].readout`` produce
        ``q0/readout/m0`` and ``q0/readout/m1`` whether or not a core ``measure`` also runs on that
        qubit. A raw-string bus carries no coordinates to build that prefix from, so it falls back
        to the bare ``m0``, ``m1``, ... counter shared by every raw-string measurement.

        Args:
            bus (str): Readout bus to acquire on.
            weights (IQWaveform | str): Integration weights, either a concrete
                :class:`~qprogram.waveforms.IQWaveform` or a string alias.
            fields (Iterable[MeasurementField]): Which measurement fields to produce, as an iterable
                of :class:`~qprogram.MeasurementField` members. Default ``(MeasurementField.IQ,)``;
                :attr:`~qprogram.MeasurementField.RAW` asks for the raw ADC trace.
            name (str | None): Explicit measurement name. Auto-allocated when omitted.

        Returns:
            The :class:`~qprogram.MeasurementHandle` this acquisition writes to, for retrieving the
            result and for referencing the outcome in a conditional.

        Raises:
            ValidationError: If ``name`` is empty, is not a string, or is already used by another
                measurement in the program, if ``fields`` names a field that is not registered, or
                if ``bus`` is a :class:`~qprogram.BusRef` from another schema than the one attached
                to the program.
        """
        return self._append_measurement(
            Acquire,
            bus=bus,
            weights=weights,
            fields=fields,
            name=name,
        )

    def set_markers(self, bus: str, mask: str) -> None:
        """Append a :class:`~qprogram_qblox.operations.SetMarkers` operation.

        Args:
            bus (str): Bus whose marker outputs to drive.
            mask (str): Four characters of ``0`` and ``1``, one per marker line, e.g. ``"0001"``.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(SetMarkers(bus=bus, mask=mask))

    def set_trigger(
        self,
        bus: str,
        duration: int,
        outputs: list[int] | int | None = None,
        position: str = "start",
    ) -> None:
        """Append a :class:`~qprogram_qblox.operations.SetTrigger` operation.

        Args:
            bus (str): Bus whose trigger outputs to arm.
            duration (int): Trigger-active duration in nanoseconds.
            outputs (list[int] | int | None): Trigger output indices to arm, one index or a list of
                them. ``None`` leaves the selection to the platform.
            position (str): Point in the operation at which the trigger fires, either ``"start"`` or
                ``"end"``. Default ``"start"``.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(SetTrigger(bus=bus, duration=duration, outputs=outputs, position=position))

    def wait_trigger(self, bus: str, duration: int, port: int | None = None) -> None:
        """Append a :class:`~qprogram_qblox.operations.WaitTrigger` operation.

        Args:
            bus (str): Bus whose sequencer waits.
            duration (int): Timeout in nanoseconds, after which the sequencer stops waiting.
            port (int | None): Trigger input port to listen on. ``None`` leaves the choice to the
                platform.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(WaitTrigger(bus=bus, duration=duration, port=port))

    def set_acquisition_threshold(self, bus: str, value: float | Expression) -> None:
        """Append a :class:`~qprogram_qblox.operations.SetAcquisitionThreshold` operation.

        Host-side-only: the platform realizes it as a slow-control parameter write at execution
        time, not as a sequencer instruction. A vendor namespace can expose operations whose effect
        is entirely off-sequencer, and the platform decides at execution time how to realize each
        one.

        Args:
            bus (str): Readout bus whose discrimination threshold to set.
            value (float | Expression): Threshold, in volts after integration. Accepts an
                :class:`~qprogram.Expression` so an enclosing loop can sweep it.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(SetAcquisitionThreshold(bus=bus, value=value))

    def set_acquisition_rotation(self, bus: str, angle: float | Expression) -> None:
        """Append a :class:`~qprogram_qblox.operations.SetAcquisitionRotation` operation.

        The companion to :meth:`set_acquisition_threshold`: the integrated IQ point is rotated by
        ``angle`` before the comparison against the threshold, so the two populations separate along
        one axis. Host-side-only as well, a parameter write rather than a sequencer instruction.

        Args:
            bus (str): Readout bus whose acquisition rotation to set.
            angle (float | Expression): Rotation angle in radians, the unit convention of core
                :meth:`~qprogram.QProgram.set_phase`. Accepts an :class:`~qprogram.Expression` so an
                enclosing loop can sweep it, which is how it is normally calibrated.

        Raises:
            ValidationError: If ``bus`` is a :class:`~qprogram.BusRef` from another schema than the
                one attached to the program.
        """
        self._append(SetAcquisitionRotation(bus=bus, angle=angle))
