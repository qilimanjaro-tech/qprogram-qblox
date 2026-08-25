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
"""Shared fixtures for the qprogram-qblox test suite."""

from __future__ import annotations

import pytest
from qprogram import BusSchema
from qprogram import QProgram as BaseQProgram

# Importing the package registers the qblox namespace, version, operations and profile.
from qprogram_qblox import QProgram as QbloxQProgram


@pytest.fixture
def transmon_schema() -> BusSchema:
    """A fresh transmon preset schema (q with drive + readout)."""
    return BusSchema.transmon()


@pytest.fixture
def empty_qblox_program() -> QbloxQProgram:
    """A QProgram with the typed ``.qblox`` property and no schema."""
    return QbloxQProgram()


@pytest.fixture
def qblox_program(transmon_schema: BusSchema) -> QbloxQProgram:
    """A QProgram with the typed ``.qblox`` property and a transmon schema attached."""
    return QbloxQProgram(schema=transmon_schema)


@pytest.fixture
def base_program(transmon_schema: BusSchema) -> BaseQProgram:
    """A core QProgram carrying no mixin, where ``.qblox`` resolves through dynamic lookup."""
    return BaseQProgram(schema=transmon_schema)
