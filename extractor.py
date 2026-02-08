"""Extraction pipeline: extracts applicability rules from AD PDFs."""
from __future__ import annotations
import re
import pdfplumber
from models import (
    AirworthinessDirective,
    ApplicabilityRules,
    MsnConstraint,
)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file."""
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n".join(pages_text)


def detect_authority(text: str, filename: str) -> str:
    """Detect whether the AD is issued by FAA or EASA."""
    text_lower = text.lower()
    if "federal aviation administration" in text_lower or "faa" in filename.upper():
        return "FAA"
    if "easa" in text_lower or "european union aviation safety agency" in text_lower:
        return "EASA"
    return "UNKNOWN"


def extract_ad_id(text: str, authority: str) -> str:
    """Extract the AD identifier from the text."""
    if authority == "FAA":
        # Pattern: AD 2025-23-53 or 2025–23–53
        match = re.search(r'AD\s+(\d{4}[-–]\d{2}[-–]\d{2,4})', text)
        if match:
            return "FAA-" + match.group(1).replace("–", "-")
    if authority == "EASA":
        match = re.search(r'AD\s+(?:No\.?\s*:?\s*)?(\d{4}[-–]\d{4}(?:R\d+)?)', text)
        if match:
            return "EASA-" + match.group(1).replace("–", "-")
    return "UNKNOWN"


def extract_aircraft_models(text: str) -> list[str]:
    """Extract aircraft model designations from the text."""
    models = set()

    # Pattern for Boeing/McDonnell Douglas models: MD-11, MD-11F, DC-10-30F, etc.
    md_dc_pattern = r'\b((?:MD|DC)-\d{1,2}(?:-\d{1,3})?[A-Z]?)\b'
    for m in re.finditer(md_dc_pattern, text):
        model = m.group(1)
        # Filter out things like DC-10 standalone when we have specific variants
        models.add(model)

    # Pattern for Airbus models: A320-214, A321-111, etc.
    airbus_pattern = r'\b(A3(?:19|20|21)-\d{3}[A-Z]?)\b'
    for m in re.finditer(airbus_pattern, text):
        models.add(m.group(1))

    return sorted(models)


def extract_service_bulletins(text: str) -> list[str]:
    """Extract service bulletin references."""
    sbs = set()
    # Pattern: SB A320-57-1089, Airbus SB A320-57-1060, etc.
    sb_pattern = r'(?:SB\s+)?(A3\d{2}-\d{2}-\d{4})'
    for m in re.finditer(sb_pattern, text):
        sbs.add("SB " + m.group(1))
    return sorted(sbs)


def extract_mod_references(text: str) -> list[str]:
    """Extract modification references (mod XXXXX)."""
    mods = set()
    mod_pattern = r'\bmod(?:ification)?\s+(\d{4,6})\b'
    for m in re.finditer(mod_pattern, text, re.IGNORECASE):
        mods.add(f"mod {m.group(1)}")
    return sorted(mods)


def extract_msn_constraints(text: str) -> MsnConstraint | None:
    """Extract MSN constraints if any are specified."""
    text_lower = text.lower()

    # Check for "all manufacturer serial numbers" or "all MSN" pattern
    if re.search(r'all\s+(?:manufacturer\s+serial\s+numbers|msn)', text_lower):
        return MsnConstraint(type="all")

    # Check for "applies to all" pattern
    if re.search(r'applies?\s+to\s+all\b', text_lower):
        return MsnConstraint(type="all")

    # Check for MSN range
    msn_range = re.search(
        r'msn\s+(\d+)\s+(?:through|to|thru|-)\s+(\d+)', text_lower
    )
    if msn_range:
        return MsnConstraint(
            type="range",
            min_msn=int(msn_range.group(1)),
            max_msn=int(msn_range.group(2)),
        )

    return MsnConstraint(type="all")


def parse_easa_applicability(text: str) -> dict:
    """Parse EASA-specific applicability details including mod/SB exclusions."""
    excluded_mods = []
    required_mods = []
    notes = []

    # Look for the Applicability section specifically
    app_match = re.search(r'Applicability:\s*(.*?)(?:Definitions:|Reason:|$)', text, re.DOTALL)
    app_text = app_match.group(1) if app_match else text

    # Pattern: "except those on which ... mod XXXXX has been embodied in production"
    except_blocks = re.finditer(
        r'except\s+those\s+on\s+which\s+(.*?)(?:;|\.|\n\n)',
        app_text, re.DOTALL | re.IGNORECASE
    )
    for block in except_blocks:
        clause = block.group(1)
        # Extract mod references
        mod_refs = re.findall(r'mod(?:ification)?\s*\(mod\)\s*(\d{4,6})', clause, re.IGNORECASE)
        if not mod_refs:
            mod_refs = re.findall(r'mod\s+(\d{4,6})', clause, re.IGNORECASE)
        if not mod_refs:
            mod_refs = re.findall(r'\(mod\)\s+(\d{4,6})', clause, re.IGNORECASE)
        for mod in mod_refs:
            context = "production" if "production" in clause.lower() else "service"
            excluded_mods.append(f"mod {mod} ({context})")

        # Extract SB references with revision
        sb_refs = re.findall(
            r'(?:SB\s+)?(A3\d{2}-\d{2}-\d{4})(?:\s+(?:at\s+)?(?:Rev(?:ision)?\s+(\d+)))?',
            clause, re.IGNORECASE
        )
        for sb_match in sb_refs:
            sb_name = sb_match[0]
            sb_rev = sb_match[1] if sb_match[1] else None
            if sb_rev:
                excluded_mods.append(f"SB {sb_name} Rev {sb_rev}")
            else:
                excluded_mods.append(f"SB {sb_name}")

    # Look for required modifications (from Required Action section)
    req_match = re.search(r'modify the aeroplane in accordance with.*?(SB\s+A3\d{2}-\d{2}-\d{4}(?:\s+Rev(?:ision)?\s+\d+)?)', text, re.IGNORECASE)
    if req_match:
        required_mods.append(req_match.group(1).strip())

    return {
        "excluded_if_modifications": sorted(set(excluded_mods)),
        "required_modifications": sorted(set(required_mods)),
        "notes": "; ".join(notes) if notes else None,
    }


def extract_from_pdf(pdf_path: str) -> AirworthinessDirective:
    """Main extraction function: PDF -> structured AD record."""
    text = extract_text_from_pdf(pdf_path)
    filename = pdf_path.split("/")[-1].split("\\")[-1]

    authority = detect_authority(text, filename)
    ad_id = extract_ad_id(text, authority)
    models = extract_aircraft_models(text)
    msn_constraint = extract_msn_constraints(text)
    service_bulletins = extract_service_bulletins(text)

    # Detect manufacturer
    manufacturer = None
    if any(m.startswith(("MD-", "DC-")) for m in models):
        manufacturer = "Boeing (McDonnell Douglas)"
    elif any(m.startswith("A3") for m in models):
        manufacturer = "Airbus S.A.S."

    # Extract subject
    subject = None
    subj_match = re.search(r'(?:Subject|ATA\s+Chapter)\s*[:\s]+\d+[,\s]*(.*?)(?:\n|$)', text)
    if subj_match:
        subject = subj_match.group(1).strip()

    # Extract effective date
    eff_date = None
    date_match = re.search(r'[Ee]ffective\s+(?:[Dd]ate)?[:\s]*([\d]{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})', text)
    if date_match:
        eff_date = date_match.group(1).strip()

    # Authority-specific parsing
    excluded_mods = []
    required_mods = []
    notes = None

    if authority == "EASA":
        easa_details = parse_easa_applicability(text)
        excluded_mods = easa_details["excluded_if_modifications"]
        required_mods = easa_details["required_modifications"]
        notes = easa_details["notes"]

    rules = ApplicabilityRules(
        aircraft_models=models,
        msn_constraints=msn_constraint,
        excluded_if_modifications=excluded_mods,
        required_modifications=required_mods,
        notes=notes,
    )

    return AirworthinessDirective(
        ad_id=ad_id,
        issuing_authority=authority,
        effective_date=eff_date,
        subject=subject,
        aircraft_manufacturer=manufacturer,
        applicability_rules=rules,
        related_service_bulletins=service_bulletins,
    )


if __name__ == "__main__":
    import json
    import sys
    import glob

    pdf_files = sys.argv[1:] if len(sys.argv) > 1 else glob.glob("*.pdf")

    for pdf_path in pdf_files:
        print(f"\n{'='*60}")
        print(f"Extracting from: {pdf_path}")
        print(f"{'='*60}")
        ad = extract_from_pdf(pdf_path)
        print(json.dumps(ad.model_dump(), indent=2, default=str))
