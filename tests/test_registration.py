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
"""Tests for the registration side effects of importing :mod:`qprogram_qblox`.

Importing the package is the activation step. It registers the vendor namespace on
:class:`~qprogram.QProgram`, the vendor protocol version, and one serialization spec per
operation. The last tests here cover the other direction: a ``.qp`` file that requires ``qblox``
reaches the installed package through its ``qprogram.vendors`` entry point, so a caller that never
imported the extension can load the file anyway.
"""

from __future__ import annotations

import importlib.metadata as md
import subprocess
import sys

from qprogram import QProgram as BaseQProgram
from qprogram.serialization.registry import (
    get_operation_spec,
    get_vendor_version,
)

import qprogram_qblox
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


def test_vendor_namespace_registered():
    """The namespace class is reachable under the ``qblox`` name on the base program."""
    assert "qblox" in BaseQProgram._vendor_registry  # type: ignore[attr-defined]
    assert BaseQProgram._vendor_registry["qblox"] is QbloxNamespace  # type: ignore[attr-defined]


def test_vendor_version_registered():
    """The protocol version the parser checks ``require qblox <x.y>`` against."""
    ver = get_vendor_version("qblox")
    assert ver is not None
    assert ver.startswith("0.")


def test_all_operations_registered():
    """Every operation the namespace can append carries a serialization spec."""
    expected = {
        "acquire": Acquire,
        "set_markers": SetMarkers,
        "set_trigger": SetTrigger,
        "wait_trigger": WaitTrigger,
        "set_acquisition_threshold": SetAcquisitionThreshold,
        "set_acquisition_rotation": SetAcquisitionRotation,
    }
    for name, cls in expected.items():
        spec = get_operation_spec("qblox", name)
        assert spec is not None, f"qblox.{name} not registered"
        assert spec.cls is cls


def test_qprogram_qblox_version_string():
    assert isinstance(qprogram_qblox.__version__, str)
    assert qprogram_qblox.__version__.count(".") >= 1


def test_qblox_pre_combined_qprogram_exists():
    assert issubclass(qprogram_qblox.QProgram, QbloxMixin)
    assert issubclass(qprogram_qblox.QProgram, BaseQProgram)


def test_qblox_declares_vendor_entry_point():
    """The ``qprogram.vendors`` group names this package under the vendor namespace.

    The entry-point name is the vendor namespace; its value is the module whose import side
    effects do the registration.
    """
    eps = {ep.name: ep.value for ep in md.entry_points(group="qprogram.vendors")}
    assert eps.get("qblox") == "qprogram_qblox"


def test_qblox_entry_point_loads_and_registers():
    """Loading the entry point imports the self-registering module and registers the version."""
    (ep,) = [e for e in md.entry_points(group="qprogram.vendors") if e.name == "qblox"]
    mod = ep.load()
    assert mod.__name__ == "qprogram_qblox"
    assert get_vendor_version("qblox") is not None


def test_qblox_autoactivates_in_fresh_process(tmp_path):
    """End-to-end self-containment: a process that imports only :mod:`qprogram` loads a file whose
    ``require qblox`` line activates the installed extension through its entry point, with no
    ``import qprogram_qblox`` anywhere.
    """
    qp_file = tmp_path / "prog.qp"
    qp_file.write_text('#!QProgram 1.0\n\nrequire qblox 0.1\n\nbody:\n  qblox.set_markers "d" "0001"\n')
    script = tmp_path / "run.py"
    script.write_text(
        "import sys, qprogram as qp\n"
        "assert 'qprogram_qblox' not in sys.modules, 'qblox was pre-imported'\n"
        f"p = qp.load({str(qp_file)!r})\n"
        "assert 'qprogram_qblox' in sys.modules, 'loads() did not auto-activate qblox'\n"
        "from qprogram_qblox.operations import SetMarkers\n"
        "assert isinstance(p.body.elements[0], SetMarkers)\n"
        "print('AUTO_OK')\n",
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "AUTO_OK" in result.stdout
