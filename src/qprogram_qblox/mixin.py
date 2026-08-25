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
"""Typed mixin that exposes the Qblox namespace as ``.qblox`` on a QProgram subclass.

The mixin exists for the benefit of editors and type-checkers. At runtime the base
:class:`~qprogram.QProgram`'s dynamic ``__getattr__`` already routes ``program.qblox.*`` to the
registered :class:`~qprogram_qblox.namespace.QbloxNamespace`, but static tooling cannot see that
dispatch, so the mixin spells the namespace out as a typed ``@property``.

One vendor, using the pre-combined class this package ships::

    from qprogram_qblox import QProgram

    qp = QProgram()  # QProgram with .qblox typed
    qp.qblox.acquire(...)  # IDE autocomplete works

Several vendors, composed by listing their mixins in the MRO::

    from qprogram import QProgram as BaseQProgram
    from qprogram_qblox import QbloxMixin
    from qprogram_qdac import QdacMixin


    class QProgram(QbloxMixin, QdacMixin, BaseQProgram):
        pass
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qprogram_qblox.namespace import QbloxNamespace

if TYPE_CHECKING:
    from qprogram.qprogram import QProgram as _BaseQProgram


class QbloxMixin:
    """Mixin that adds a typed ``.qblox`` property to QProgram.

    Compose it with :class:`qprogram.QProgram` through multiple inheritance to get editor
    autocomplete for the Qblox operations. The property caches the namespace on the program, so
    repeated ``program.qblox`` accesses return the same object.
    """

    @property
    def qblox(self: _BaseQProgram) -> QbloxNamespace:  # type: ignore[misc]
        """This program's typed Qblox namespace.

        The first access builds a :class:`~qprogram_qblox.namespace.QbloxNamespace` bound to the
        program and stores it under a private attribute; later accesses return that same instance.
        Both the load and the store go through :class:`object` so they bypass the program's own
        attribute hooks: a cache miss has to surface as a plain :exc:`AttributeError` here rather
        than reach :class:`~qprogram.QProgram`'s vendor-registry ``__getattr__``.
        """
        try:
            return object.__getattribute__(self, "_qblox_ns")  # ruff: ignore[unnecessary-dunder-call]
        except AttributeError:
            pass
        ns = QbloxNamespace(self)
        object.__setattr__(self, "_qblox_ns", ns)  # ruff: ignore[unnecessary-dunder-call]
        return ns
