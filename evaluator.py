"""Evaluation code: determines if an aircraft is affected by an AD."""
from __future__ import annotations
import re
from models import AircraftConfig, AirworthinessDirective


def normalize_model(model: str) -> str:
    """Normalize model string for comparison."""
    return model.strip().upper().replace(" ", "-").replace("–", "-")


def model_matches(aircraft_model: str, ad_models: list[str]) -> bool:
    """Check if an aircraft model matches any of the AD's applicable models."""
    norm_aircraft = normalize_model(aircraft_model)

    for ad_model in ad_models:
        norm_ad = normalize_model(ad_model)
        if norm_aircraft == norm_ad:
            return True
        # Handle cases like "Boeing 737-800" matching "737-800"
        if norm_aircraft.endswith(norm_ad) or norm_ad.endswith(norm_aircraft):
            return True

    return False


def msn_matches(msn: int, msn_constraint) -> bool:
    """Check if an MSN falls within the AD's MSN constraints."""
    if msn_constraint is None or msn_constraint.type == "all":
        return True
    if msn_constraint.type == "range":
        min_msn = msn_constraint.min_msn or 0
        max_msn = msn_constraint.max_msn or float("inf")
        return min_msn <= msn <= max_msn
    if msn_constraint.type == "list":
        return msn in (msn_constraint.values or [])
    return True


def has_excluding_modification(
    aircraft_mods: list[str], excluded_mods: list[str]
) -> bool:
    """Check if the aircraft has any modification that excludes it from the AD."""
    for aircraft_mod in aircraft_mods:
        am_lower = aircraft_mod.strip().lower()
        for exc in excluded_mods:
            exc_lower = exc.strip().lower()
            # Remove context like "(production)" or "(service)" for comparison
            exc_base = exc_lower.split("(")[0].strip()
            # Check various match patterns
            if am_lower == exc_lower or am_lower == exc_base:
                return True
            # Partial: "mod 24591" matches "mod 24591 (production)"
            if exc_base in am_lower or am_lower in exc_base:
                return True
            # SB matching: "SB A320-57-1089 Rev 04" should match "SB A320-57-1089 Rev 04"
            # Also "SB A320-57-1089" in aircraft mods should match "SB A320-57-1089 Rev 04" in exclusions
            if "sb " in am_lower and "sb " in exc_base:
                # Extract SB number from both
                am_sb = re.search(r'(a3\d{2}-\d{2}-\d{4})', am_lower)
                exc_sb = re.search(r'(a3\d{2}-\d{2}-\d{4})', exc_base)
                if am_sb and exc_sb and am_sb.group(1) == exc_sb.group(1):
                    # SB numbers match, now check revision
                    am_rev = re.search(r'rev(?:ision)?\s*(\d+)', am_lower)
                    exc_rev = re.search(r'rev(?:ision)?\s*(\d+)', exc_base)
                    if exc_rev and am_rev:
                        # Both have revisions, must match
                        if am_rev.group(1) == exc_rev.group(1):
                            return True
                    elif exc_rev and not am_rev:
                        # Exclusion specifies rev but aircraft mod doesn't — still match
                        return True
                    elif not exc_rev:
                        # Exclusion doesn't specify rev — any rev matches
                        return True
    return False


def is_affected(aircraft: AircraftConfig, ad: AirworthinessDirective) -> bool:
    """
    Determine if a specific aircraft configuration is affected by an AD.

    Returns True if the aircraft IS affected (needs action).
    Returns False if the aircraft is NOT affected/applicable.
    """
    rules = ad.applicability_rules

    # Step 1: Check if aircraft model is in the AD's applicability
    if not model_matches(aircraft.aircraft_model, rules.aircraft_models):
        return False

    # Step 2: Check MSN constraints
    if not msn_matches(aircraft.msn, rules.msn_constraints):
        return False

    # Step 3: Check if aircraft has a modification that excludes it
    if aircraft.modifications_applied and rules.excluded_if_modifications:
        if has_excluding_modification(
            aircraft.modifications_applied, rules.excluded_if_modifications
        ):
            return False

    return True


def evaluate_aircraft(
    aircraft: AircraftConfig, ads: list[AirworthinessDirective]
) -> dict[str, str]:
    """Evaluate an aircraft against multiple ADs."""
    results = {}
    for ad in ads:
        affected = is_affected(aircraft, ad)
        results[ad.ad_id] = "Affected" if affected else "Not applicable"
    return results
