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
"""Qblox vendor extensions for QProgram.

This package provides:

1. **Runtime registration**: importing this package registers the ``qblox`` vendor namespace on
   :class:`~qprogram.QProgram`, registers every Qblox operation with the ``.qp`` serializer, and
   registers the ``qblox-default-v1`` capability profile.

2. **Typed mixin**: :class:`QbloxMixin` adds a typed ``.qblox`` property for IDE autocomplete.

3. **Pre-combined QProgram**: :class:`QProgram` from this package has ``.qblox`` typed out of the
   box.

The import is the activation step, and a caller reading a ``.qp`` file need not perform it: the
``qprogram.vendors`` entry point this package declares lets :func:`qprogram.loads` import the module
on demand when it meets a ``require qblox`` header.

The operations span both kinds a vendor extension can offer, since QProgram draws no line between
real-time and host-side execution:

- one-to-one sequencer instructions (:meth:`QbloxNamespace.acquire`,
  :meth:`QbloxNamespace.set_markers`, :meth:`QbloxNamespace.set_trigger`,
  :meth:`QbloxNamespace.wait_trigger`);
- host-side-only operations (:meth:`QbloxNamespace.set_acquisition_threshold`,
  :meth:`QbloxNamespace.set_acquisition_rotation`), each a slow-control parameter write at execution
  time rather than a sequencer instruction.

Both spell the same way in ``.qp`` (``qblox.<op_name> <args>``); the platform decides at execution
time how to realize each one. A third kind is possible and is not among the operations here: an
orchestration that lowers to several instructions. Routing a measurement result back to a drive
sequencer, for instance, is a property of the platform wiring rather than of the qblox instrument
API, so it belongs to a platform package instead.

The shortest way in is the pre-combined class::

    from qprogram_qblox import QProgram

    qp = QProgram(label="example")
    qp.qblox.acquire("readout_q0", "weights")
    qp.qblox.set_markers("drive_q0", "0001")
    qp.qblox.set_acquisition_threshold("readout_q0", value=0.42)
    qp.qblox.set_acquisition_rotation("readout_q0", angle=0.7854)

Combining several vendors means listing their mixins in the MRO::

    from qprogram import QProgram as BaseQProgram
    from qprogram_qblox import QbloxMixin
    from qprogram_qdac import QdacMixin


    class QProgram(QbloxMixin, QdacMixin, BaseQProgram):
        pass


    qp = QProgram()
    qp.qblox.acquire(...)
    qp.qdac.play(...)

A ``.qp`` file carrying qblox operations names the vendor in its header::

    #!QProgram 1.0

    require qblox 0.1

    body:
      qblox.acquire "readout_q0" "weights"
      qblox.set_markers "drive_q0" "0001"
"""

from importlib.metadata import PackageNotFoundError, version

from qprogram.qprogram import QProgram as _BaseQProgram
from qprogram.serialization._specs import make_measurement_op_parse, measurement_op_serialize
from qprogram.serialization.registry import register_vendor_operation, register_vendor_version

from qprogram_qblox.mixin import QbloxMixin
from qprogram_qblox.namespace import QbloxNamespace
from qprogram_qblox.operations import (
    Acquire,
    SetAcquisitionRotation,
    SetAcquisitionThreshold,
    SetMarkers,
    SetTrigger,
    WaitTrigger,
)
from qprogram_qblox.profiles import QBLOX_DEFAULT_V1
from qprogram_qblox.profiles import _register as _register_qblox_profile

# Resolve our own package version once. This is the single source of truth for the qblox vendor
# protocol version: parsers check that a file's `require qblox <major.minor>` is compatible with
# this number.
try:
    __version__ = version("qprogram-qblox")
except PackageNotFoundError:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0"

# --- Step 1: Register the vendor namespace on base QProgram ---
# Registering on the base class is what makes program.qblox.<method>() work on any QProgram
# instance, mixin or not.
_BaseQProgram.register_vendor("qblox", QbloxNamespace)

# --- Step 2: Register the protocol version of this vendor extension ---
# The .qp parser checks `require qblox <x.y>` against it.
register_vendor_version("qblox", __version__)

# --- Step 3: Register operations with the .qp serializer ---
# All but `acquire` use the default signature-driven serialize/parse pair. `acquire` is a
# measurement operation, so it needs the measurement callbacks that carry the handle name across
# the wire as a `name="..."` kwarg.
register_vendor_operation(
    "qblox",
    "acquire",
    Acquire,
    serialize=measurement_op_serialize,
    parse=make_measurement_op_parse(Acquire),
)
register_vendor_operation("qblox", "set_markers", SetMarkers)
register_vendor_operation("qblox", "set_trigger", SetTrigger)
register_vendor_operation("qblox", "wait_trigger", WaitTrigger)
register_vendor_operation("qblox", "set_acquisition_threshold", SetAcquisitionThreshold)
register_vendor_operation("qblox", "set_acquisition_rotation", SetAcquisitionRotation)

# --- Step 4: Register the qblox capability profile bundle ---
# Importing qprogram_qblox.profiles above already registered the vendor capability tokens, which is
# what lets the profile name them.
_register_qblox_profile()


class QProgram(QbloxMixin, _BaseQProgram):
    """:class:`~qprogram.QProgram` pre-combined with :class:`QbloxMixin`.

    Identical to :class:`qprogram.QProgram` but with IDE autocomplete for ``qp.qblox.*``.
    """


__all__ = [
    "QBLOX_DEFAULT_V1",
    "Acquire",
    "QProgram",
    "QbloxMixin",
    "QbloxNamespace",
    "SetAcquisitionRotation",
    "SetAcquisitionThreshold",
    "SetMarkers",
    "SetTrigger",
    "WaitTrigger",
]
