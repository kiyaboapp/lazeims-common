"""Versioned station package manifest contract (``station-package/v1``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "station-package/v1"


class PackageScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schools: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    papers: list[str] = Field(default_factory=list)


class StationPackageManifest(BaseModel):
    """Produced by Central, consumed by the station on first setup.

    Every id here is a natural key (centre number, subject code, paper type) —
    never a database integer id.
    """

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=CONTRACT_VERSION)
    package_id: str
    package_version: int
    rules_version: str
    software_min_version: str
    station_code: str
    exam_id: str
    configuration_hash: str
    issued_at: datetime
    scope: PackageScope
