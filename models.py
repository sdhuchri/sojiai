"""Pydantic models for structured AD applicability rules."""
from __future__ import annotations
from pydantic import BaseModel


class MsnConstraint(BaseModel):
    """MSN range or list constraint."""
    type: str  # "all", "range", "list"
    values: list[int] | None = None
    min_msn: int | None = None
    max_msn: int | None = None


class ApplicabilityRules(BaseModel):
    """Structured applicability rules extracted from an AD."""
    aircraft_models: list[str]
    msn_constraints: MsnConstraint | None = None
    excluded_if_modifications: list[str] = []
    required_modifications: list[str] = []
    notes: str | None = None


class AirworthinessDirective(BaseModel):
    """Full AD record with metadata and applicability rules."""
    ad_id: str
    issuing_authority: str  # "FAA" or "EASA"
    effective_date: str | None = None
    subject: str | None = None
    aircraft_manufacturer: str | None = None
    applicability_rules: ApplicabilityRules
    related_service_bulletins: list[str] = []


class AircraftConfig(BaseModel):
    """An aircraft configuration to evaluate against ADs."""
    aircraft_model: str
    msn: int
    modifications_applied: list[str] = []
