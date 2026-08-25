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
"""Tests for :class:`~qprogram_qblox.QbloxMixin`, the typed-property half of the vendor hook.

The mixin is there for editors: it declares ``.qblox`` as a property so autocomplete and type
checking see the namespace. A program without the mixin reaches the same namespace through
:meth:`~qprogram.QProgram.__getattr__`, and mixins from several vendors compose in one class.
"""

from __future__ import annotations

from qprogram import QProgram as BaseQProgram
from qprogram.vendor import VendorNamespace

from qprogram_qblox import QProgram as QbloxQProgram
from qprogram_qblox.mixin import QbloxMixin
from qprogram_qblox.namespace import QbloxNamespace


def test_qprogram_subclasses_mixin():
    assert issubclass(QbloxQProgram, QbloxMixin)
    assert issubclass(QbloxQProgram, BaseQProgram)


def test_mixin_property_returns_namespace(empty_qblox_program):
    assert isinstance(empty_qblox_program.qblox, QbloxNamespace)


def test_mixin_property_caches_per_instance(empty_qblox_program):
    first = empty_qblox_program.qblox
    second = empty_qblox_program.qblox
    assert first is second


def test_mixin_namespace_distinct_per_instance():
    qp1 = QbloxQProgram()
    qp2 = QbloxQProgram()
    assert qp1.qblox is not qp2.qblox


def test_base_qprogram_resolves_namespace_dynamically(base_program):
    """``.qblox`` is reachable on a program that does not carry the mixin."""
    ns = base_program.qblox  # type: ignore[attr-defined]
    assert isinstance(ns, QbloxNamespace)


def test_mixin_multiple_vendor_composition():
    """Mixins compose through the MRO, so one program class can carry two vendor properties."""

    class FakeNS(VendorNamespace):
        pass

    BaseQProgram.register_vendor("fake", FakeNS)

    class FakeMixin:
        @property
        def fake(self) -> FakeNS:
            return FakeNS(self)  # type: ignore[arg-type]

    class Combined(QbloxMixin, FakeMixin, BaseQProgram):
        pass

    qp = Combined()
    assert isinstance(qp.qblox, QbloxNamespace)
    assert isinstance(qp.fake, FakeNS)
