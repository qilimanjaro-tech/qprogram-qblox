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
"""Typed [`VendorNamespace`][qprogram.VendorNamespace] for Qblox operations.

Each method on [`QbloxNamespace`][qprogram_qblox.QbloxNamespace] is a typed wrapper that builds the matching
[`Operation`][qprogram.operations.Operation] subclass from `qprogram_qblox.operations` and appends
it to the program's active block. This is where explicit parameter types live, so editors complete
and type-checkers check ``program.qblox.<operation>(...)``. The dynamic ``__getattr__`` on
[`QProgram`][qprogram.QProgram] dispatches the same calls at runtime; the typed namespace is what makes
them discoverable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qprogram.errors import ValidationError
from qprogram.operations.operation import MeasurementField
from qprogram.vendor import VendorNamespace

from qprogram_qblox.operations import (
    Acquire,
    Scope,
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

    Attached to every [`QProgram`][qprogram.QProgram] instance as ``.qblox`` once the
    `qprogram_qblox` package is imported. Each method validates its arguments through the typed
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
        """Append an [`Acquire`][qprogram_qblox.Acquire] operation.

        The handle's name comes from the same per-bus counter core
        [`measure`][qprogram.QProgram.measure] draws on, so two acquisitions on ``q[0].readout`` produce
        ``q0/readout/m0`` and ``q0/readout/m1`` whether or not a core ``measure`` also runs on that
        qubit. A raw-string bus carries no coordinates to build that prefix from, so it falls back
        to the bare ``m0``, ``m1``, ... counter shared by every raw-string measurement.

        Args:
            bus (str): Readout bus to acquire on.
            weights (IQWaveform | str): Integration weights, either a concrete
                [`IQWaveform`][qprogram.waveforms.IQWaveform] or a string alias.
            fields (Iterable[MeasurementField]): Which measurement fields to produce, as an iterable
                of [`MeasurementField`][qprogram.MeasurementField] members. Default ``(MeasurementField.IQ,)``.
                A qblox bus produces `IQ` and `STATE`. `RAW` builds, but fails validation against
                ``qblox-default-v1`` with ``missing-capability``; record the raw trace with
                [`scope`][qprogram_qblox.QbloxNamespace.scope] instead.
            name (str | None): Explicit measurement name. Auto-allocated when omitted.

        Returns:
            The [`MeasurementHandle`][qprogram.MeasurementHandle] this acquisition writes to, for retrieving the
            result and for referencing the outcome in a conditional.

        Raises:
            ValidationError: If ``name`` is empty, is not a string, or is already used by another
                measurement in the program, if ``fields`` names a field that is not registered, or
                if ``bus`` is a [`BusRef`][qprogram.BusRef] from another schema than the one attached
                to the program.
        """
        return self._append_measurement(
            Acquire,
            bus=bus,
            weights=weights,
            fields=fields,
            name=name,
        )

    def scope(
        self,
        bus: str,
        *,
        averaging: bool = True,
        trigger_level: float | None = None,
        name: str | None = None,
    ) -> MeasurementHandle:
        """Append a [`Scope`][qprogram_qblox.Scope] operation.

        The acquisitions on ``bus`` then trigger the scope of its QRM for the whole run, wherever the
        call sits in the program. Read the trace back with ``result.get(handle, field="raw")``, or by
        name when the handle is out of reach, for example when the program is built in another module.

        Scopes are named ``scope0``, ``scope1``, ... in declaration order, skipping names already in
        use. The counter is separate from the ``m0``, ``m1``, ... one, so adding or removing a scope
        never renames an acquisition.

        Args:
            bus (str): Readout bus whose acquisitions trigger the scope. Its QRM is the module scoped.
            averaging (bool): ``True`` adds every trigger into the scope buffer and divides by their
                count. ``False`` keeps only the last trigger. Default ``True``.
            trigger_level (float | None): ``None`` triggers on the sequencer's acquisitions. A number
                in ``[-1, 1]`` triggers when the input crosses that level instead. Default ``None``.
            name (str | None): Explicit measurement name. Auto-allocated when omitted.

        Returns:
            The [`MeasurementHandle`][qprogram.MeasurementHandle] the trace is stored under.

        Raises:
            ValidationError: If ``bus`` is already scoped in this program, if ``trigger_level`` is
                not ``None`` or a number in ``[-1, 1]``, if ``name`` is empty, is not a string, or is
                already used by another measurement in the program, or if ``bus`` is a
                [`BusRef`][qprogram.BusRef] from another schema than the one attached to the program.
        """
        if any(isinstance(node, Scope) and node.bus == bus for node in self._program.body.walk()):
            msg = f"bus {bus!r} is already scoped in this program; a QRM has one scope, so scope each bus once"
            raise ValidationError(msg)
        if name is None:
            used_names = {handle.name for handle in self._program.measurement_handles()}
            n = 0
            while f"scope{n}" in used_names:
                n += 1
            name = f"scope{n}"
        return self._append_measurement(
            Scope,
            bus=bus,
            averaging=averaging,
            trigger_level=trigger_level,
            name=name,
        )

    def set_markers(self, bus: str, mask: str) -> None:
        """Append a [`SetMarkers`][qprogram_qblox.SetMarkers] operation.

        Args:
            bus (str): Bus whose marker outputs to drive.
            mask (str): Four characters of ``0`` and ``1``, one per marker line, e.g. ``"0001"``.

        Raises:
            ValidationError: If ``bus`` is a [`BusRef`][qprogram.BusRef] from another schema than the
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
        """Append a [`SetTrigger`][qprogram_qblox.SetTrigger] operation.

        Args:
            bus (str): Bus whose trigger outputs to arm.
            duration (int): Trigger-active duration in nanoseconds.
            outputs (list[int] | int | None): Trigger output indices to arm, one index or a list of
                them. ``None`` leaves the selection to the platform.
            position (str): Point in the operation at which the trigger fires, either ``"start"`` or
                ``"end"``. Default ``"start"``.

        Raises:
            ValidationError: If ``bus`` is a [`BusRef`][qprogram.BusRef] from another schema than the
                one attached to the program.
        """
        self._append(SetTrigger(bus=bus, duration=duration, outputs=outputs, position=position))

    def wait_trigger(self, bus: str, duration: int, port: int | None = None) -> None:
        """Append a [`WaitTrigger`][qprogram_qblox.WaitTrigger] operation.

        Args:
            bus (str): Bus whose sequencer waits.
            duration (int): Timeout in nanoseconds, after which the sequencer stops waiting.
            port (int | None): Trigger input port to listen on. ``None`` leaves the choice to the
                platform.

        Raises:
            ValidationError: If ``bus`` is a [`BusRef`][qprogram.BusRef] from another schema than the
                one attached to the program.
        """
        self._append(WaitTrigger(bus=bus, duration=duration, port=port))

    def set_acquisition_threshold(self, bus: str, value: float | Expression) -> None:
        """Append a [`SetAcquisitionThreshold`][qprogram_qblox.SetAcquisitionThreshold] operation.

        Host-side-only: the platform realizes it as a slow-control parameter write at execution
        time, not as a sequencer instruction. A vendor namespace can expose operations whose effect
        is entirely off-sequencer, and the platform decides at execution time how to realize each
        one.

        Args:
            bus (str): Readout bus whose discrimination threshold to set.
            value (float | Expression): Threshold, in volts after integration. Accepts an
                [`Expression`][qprogram.Expression] so an enclosing loop can sweep it.

        Raises:
            ValidationError: If ``bus`` is a [`BusRef`][qprogram.BusRef] from another schema than the
                one attached to the program.
        """
        self._append(SetAcquisitionThreshold(bus=bus, value=value))

    def set_acquisition_rotation(self, bus: str, angle: float | Expression) -> None:
        """Append a [`SetAcquisitionRotation`][qprogram_qblox.SetAcquisitionRotation] operation.

        The companion to `set_acquisition_threshold`: the integrated IQ point is rotated by
        ``angle`` before the comparison against the threshold, so the two populations separate along
        one axis. Host-side-only as well, a parameter write rather than a sequencer instruction.

        Args:
            bus (str): Readout bus whose acquisition rotation to set.
            angle (float | Expression): Rotation angle in radians, the unit convention of core
                [`set_phase`][qprogram.QProgram.set_phase]. Accepts an [`Expression`][qprogram.Expression] so an
                enclosing loop can sweep it, which is how it is normally calibrated.

        Raises:
            ValidationError: If ``bus`` is a [`BusRef`][qprogram.BusRef] from another schema than the
                one attached to the program.
        """
        self._append(SetAcquisitionRotation(bus=bus, angle=angle))
