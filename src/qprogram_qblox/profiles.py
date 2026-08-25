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
"""Capability profile bundles for the Qblox vendor extension.

Defines :data:`QBLOX_DEFAULT_V1`, the bus-level profile describing what a qblox-driven bus can do:
the pulse, timing and parameter operations, every waveform class the sequencers render, the
measurement fields a readout produces, and the ``vendor.qblox.*`` operations. Qblox drives its
sequencers in real time, so a platform fills a bus slot's ``rt`` half with it; the platform slot is
filled by the core-shipped ``qprogram-base-v1``, which carries the block, sweep and expression
tokens. Together the two give a complete :class:`~qprogram.PlatformCapabilities` shape.

Two predicates travel with the profile:

- :func:`_reject_arbitrary_sweep_at_wait_duration`, a hard :class:`~qprogram.Diagnostic`. The
  operand register of the qblox wait instruction advances by a fixed step, so a duration swept from
  an arbitrary source fits no execution model qblox can compile, real-time or host-side.
- :func:`_drag_sigma_in_loop_is_host_only`, a soft :class:`~qprogram.DomainConstraint`. The
  sequencer cannot recompute an :class:`~qprogram.waveforms.IQDrag` envelope between iterations, but
  the host can dispatch one shot per iteration. The constraint excludes ``"rt"`` alone, so the
  binding loop classifies as ``{host}`` while the ``play`` inside it stays real-time.

Registered as a side effect of importing :mod:`qprogram_qblox`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qprogram.operations.play import Play
from qprogram.operations.wait import Wait
from qprogram.protocol import (
    Diagnostic,
    DomainConstraint,
    Profile,
    ValidationContext,
    register_capability_tokens,
    register_profile,
)
from qprogram.variable import Variable
from qprogram.waveforms.iq_drag import IQDrag

# Register vendor-specific capability tokens *before* constructing the profile that names them:
# Profile.__post_init__ validates that every listed token is in CAPABILITY_REGISTRY, so registration
# must come first.
register_capability_tokens(
    "vendor.qblox.acquire",
    "vendor.qblox.set_markers",
    "vendor.qblox.set_trigger",
    "vendor.qblox.wait_trigger",
    "vendor.qblox.set_acquisition_threshold",
    "vendor.qblox.set_acquisition_rotation",
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qprogram.blocks.block import Block
    from qprogram.operations.operation import Operation


def _reject_arbitrary_sweep_at_wait_duration(
    node: Operation | Block,
    ctx: ValidationContext,
) -> Iterable[Diagnostic | DomainConstraint]:
    """Reject a ``wait`` whose duration is bound to an arbitrary sweep source.

    The qblox wait instruction takes one integer cycle count, and the register holding it advances
    by a fixed step, so the hardware can only walk a duration that is an exact ``start + step * i``
    ramp. The predicate asks :meth:`~qprogram.ValidationContext.sweep_kind_of` how the variable at
    :attr:`~qprogram.operations.Wait.duration` is bound and fires when the binding
    :class:`~qprogram.blocks.Sweep`'s source declares ``KIND = "arbitrary"``:
    :class:`~qprogram.sweeps.Values`, :class:`~qprogram.sweeps.Logspace`,
    :class:`~qprogram.sweeps.File`, and every combinator around them. A linear source
    (:class:`~qprogram.sweeps.Range`, :class:`~qprogram.sweeps.Linspace`) passes, and so does a
    constant duration, which is not loop-bound at all.

    Host-side dispatch cannot rescue the combination, since qblox still has to emit the wait
    instruction per shot. That is why this is a :class:`~qprogram.Diagnostic` rather than a
    :class:`~qprogram.DomainConstraint`.

    Args:
        node (Operation | Block): The AST node currently being checked.
        ctx (ValidationContext): Validation context, used to look up how the duration variable is
            bound.

    Yields:
        One ``"qblox.arbitrary-wait-sweep"`` error :class:`~qprogram.Diagnostic` when ``node`` is a
        ``wait`` whose duration variable is bound to an arbitrary source. Nothing otherwise.
    """
    if not isinstance(node, Wait):
        return
    if not isinstance(node.duration, Variable):
        return
    if ctx.sweep_kind_of(node.duration) == "arbitrary":
        yield Diagnostic(
            severity="error",
            code="qblox.arbitrary-wait-sweep",
            message=(
                f"Variable {node.duration.id!r} is swept with arbitrary "
                f"values and used at Wait.duration, which qblox does not "
                f"support (the wait instruction needs a linear step). Use "
                f"a linear sweep source (Range / Linspace) instead, or a constant duration."
            ),
            node=node,
        )


def _drag_sigma_in_loop_is_host_only(
    node: Operation | Block,
    ctx: ValidationContext,
) -> Iterable[Diagnostic | DomainConstraint]:
    """Restrict the binding loop of a swept ``IQDrag.sigma`` to host-side dispatch.

    A qblox sequencer re-arms a real-time loop with a new amplitude or duration on its own, but it
    cannot recompute a Drag envelope's ``sigma`` between iterations: the gaussian and its derivative
    are sampled once, at upload. Sweeping ``sigma`` therefore means re-uploading the waveform per
    iteration, which the enclosing loop can only do host-side, one qblox shot at a time. The
    :class:`~qprogram.operations.Play` itself stays real-time; what changes is how the loop around it
    iterates.

    The constraint targets the loop returned by :meth:`~qprogram.ValidationContext.binding_loop_of`,
    not the ``Play``, because that is the node whose iteration mechanism is at stake. The classifier
    subtracts ``"rt"`` from the loop's support and dispatches the ``Play`` as one real-time shot per
    host-side iteration. A ``sigma`` that no loop binds is a constant at upload time and is left
    alone.

    Args:
        node (Operation | Block): The AST node currently being checked.
        ctx (ValidationContext): Validation context, used to find the loop that binds ``sigma``.

    Yields:
        One :class:`~qprogram.DomainConstraint` excluding ``"rt"`` from the binding loop, when
        ``node`` is a ``play`` of an :class:`~qprogram.waveforms.IQDrag` whose ``sigma`` is a
        loop-bound variable. Nothing otherwise.
    """
    if not isinstance(node, Play) or not isinstance(node.waveform, IQDrag):
        return
    sigma = node.waveform.sigma
    if not isinstance(sigma, Variable):
        return
    binding_loop = ctx.binding_loop_of(sigma)
    if binding_loop is None:
        return
    yield DomainConstraint(
        node=binding_loop,
        exclude=frozenset({"rt"}),
        reason=(
            f"Variable {sigma.id!r} sweeps IQDrag.sigma in a contained Play, which qblox "
            f"cannot real-time-update; the loop dispatches per shot host-side instead."
        ),
    )


_BUS_OPS: frozenset[str] = frozenset(
    {
        "op.play",
        "op.measure",
        "op.wait",
        "op.sync",
        "op.set_frequency",
        "op.set_phase",
        "op.set_gain",
        "op.reset_phase",
        "op.set_offset",
    },
)
"""Core operations a qblox sequencer executes.

Each of them targets a bus, so its token belongs on this bus-level profile rather than on the
platform slot: the validator routes a bus-touching operation to the slot its bus resolves to.
"""

_WAVEFORMS: frozenset[str] = frozenset(
    {
        "waveform.single",
        "waveform.iq",
        "waveform.alias",
        "waveform.arbitrary",
        "waveform.chained",
        "waveform.flat_top",
        "waveform.gaussian",
        "waveform.gaussian_drag_correction",
        "waveform.ramp",
        "waveform.snz",
        "waveform.square",
        "waveform.iq_drag",
        "waveform.iq_pair",
    },
)
"""Waveform tokens the qblox sequencers render.

Two levels, both bus-level because a waveform only reaches the hardware through a bus: the channel
kind (``waveform.single`` and ``waveform.iq``, since qblox drives both single-channel and IQ buses),
``waveform.alias`` for a name a :class:`~qprogram.WaveformLibrary` resolves later, and one per-class
token for each envelope the sequencers can sample.
"""

_FIELDS: frozenset[str] = frozenset(
    {
        "measure.fields.iq",
        "measure.fields.raw",
        "measure.fields.state",
    },
)
"""Measurement fields a qblox readout produces.

All three core members of :class:`~qprogram.MeasurementField`: the integrated IQ point, the raw ADC
trace, and the thresholded state. :class:`~qprogram.operations.Measure` and
:meth:`~qprogram_qblox.QbloxNamespace.acquire` attach a ``measure.fields.<name>`` token per
requested field and both target a bus, which is why the tokens are bus-level.
"""

_VENDOR: frozenset[str] = frozenset(
    {
        "vendor.qblox.acquire",
        "vendor.qblox.set_markers",
        "vendor.qblox.set_trigger",
        "vendor.qblox.wait_trigger",
        "vendor.qblox.set_acquisition_threshold",
        "vendor.qblox.set_acquisition_rotation",
    },
)
"""The ``vendor.qblox.*`` operation tokens.

Every operation this package ships carries a ``bus``, so all six route to the bus slot. A bus-less
vendor operation would need its token on the platform slot instead.
"""


QBLOX_DEFAULT_V1 = Profile(
    name="qblox-default-v1",
    version=(0, 1, 0),
    extends=None,
    capabilities=_BUS_OPS | _WAVEFORMS | _FIELDS | _VENDOR,
    limits={"min_wait_duration_ns": 4},
    predicates=(
        _reject_arbitrary_sweep_at_wait_duration,
        _drag_sigma_in_loop_is_host_only,
    ),
    vendor_versions={"qblox": (0, 1, 0)},
)
"""The default Qblox bus-level capability profile.

Holds every token a qblox-driven bus accepts (:data:`_BUS_OPS`, :data:`_WAVEFORMS`, :data:`_FIELDS`
and :data:`_VENDOR`), the ``min_wait_duration_ns`` floor of the wait instruction, and the two
predicates above. It carries no ``block.*``, ``sweep.*`` or ``expr.*`` token: those route to the
platform slot, which a qblox platform fills from ``qprogram-base-v1``.

Reach it by name with
``CompilerCapabilities.from_profile("qblox-default-v1", limit_overrides=...)``, or extend it with a
profile of your own that declares ``extends="qblox-default-v1"`` and lists only what differs.
"""


def _register() -> None:
    """Idempotently register :data:`QBLOX_DEFAULT_V1` on the global profile registry."""
    register_profile(QBLOX_DEFAULT_V1)


__all__ = ["QBLOX_DEFAULT_V1"]
