"""Main pipeline: extract rules from PDFs and evaluate aircraft configurations."""
from __future__ import annotations
import json
import glob
from extractor import extract_from_pdf
from evaluator import evaluate_aircraft, is_affected
from models import AircraftConfig


# ── Test aircraft configurations from the assignment ──
TEST_AIRCRAFT = [
    AircraftConfig(aircraft_model="MD-11", msn=48123, modifications_applied=[]),
    AircraftConfig(aircraft_model="DC-10-30F", msn=47890, modifications_applied=[]),
    AircraftConfig(aircraft_model="Boeing 737-800", msn=30123, modifications_applied=[]),
    AircraftConfig(aircraft_model="A320-214", msn=5234, modifications_applied=[]),
    AircraftConfig(aircraft_model="A320-232", msn=6789, modifications_applied=["mod 24591"]),
    AircraftConfig(aircraft_model="A320-214", msn=7456, modifications_applied=["SB A320-57-1089 Rev 04"]),
    AircraftConfig(aircraft_model="A321-111", msn=8123, modifications_applied=[]),
    AircraftConfig(aircraft_model="A321-112", msn=364, modifications_applied=["mod 24977"]),
    AircraftConfig(aircraft_model="A319-100", msn=9234, modifications_applied=[]),
    AircraftConfig(aircraft_model="MD-10-10F", msn=46234, modifications_applied=[]),
]

# ── Verification examples ──
VERIFICATION = [
    {"aircraft": AircraftConfig(aircraft_model="MD-11F", msn=48400, modifications_applied=[]),
     "expected": {"FAA-2025-23-53": "Affected", "EASA-2025-0254R1": "Not applicable"}},
    {"aircraft": AircraftConfig(aircraft_model="A320-214", msn=4500, modifications_applied=["mod 24591"]),
     "expected": {"FAA-2025-23-53": "Not applicable", "EASA-2025-0254R1": "Not affected"}},
    {"aircraft": AircraftConfig(aircraft_model="A320-214", msn=4500, modifications_applied=[]),
     "expected": {"FAA-2025-23-53": "Not applicable", "EASA-2025-0254R1": "Affected"}},
]


def main():
    # ── Step 1: Extract rules from PDFs ──
    print("=" * 70)
    print("STEP 1: EXTRACTING APPLICABILITY RULES FROM PDFs")
    print("=" * 70)

    pdf_files = sorted(glob.glob("*.pdf"))
    if not pdf_files:
        print("ERROR: No PDF files found in current directory.")
        return

    ads = []
    for pdf_path in pdf_files:
        print(f"\nProcessing: {pdf_path}")
        ad = extract_from_pdf(pdf_path)
        ads.append(ad)
        print(f"  AD ID: {ad.ad_id}")
        print(f"  Authority: {ad.issuing_authority}")
        print(f"  Models: {ad.applicability_rules.aircraft_models}")
        print(f"  MSN constraint: {ad.applicability_rules.msn_constraints}")
        print(f"  Excluded if mods: {ad.applicability_rules.excluded_if_modifications}")
        print(f"  Service bulletins: {ad.related_service_bulletins}")

    # Save structured output
    output = [ad.model_dump() for ad in ads]
    with open("extracted_rules.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nStructured rules saved to: extracted_rules.json")

    # ── Step 2: Evaluate test aircraft ──
    print("\n" + "=" * 70)
    print("STEP 2: EVALUATING AIRCRAFT CONFIGURATIONS")
    print("=" * 70)

    # Table header
    ad_ids = [ad.ad_id for ad in ads]
    header = f"{'Aircraft Model':<18} {'MSN':<8} {'Modifications':<30}"
    for ad_id in ad_ids:
        header += f" {ad_id:<22}"
    print(f"\n{header}")
    print("-" * len(header))

    results_table = []
    for ac in TEST_AIRCRAFT:
        mods_str = ", ".join(ac.modifications_applied) if ac.modifications_applied else "None"
        row = f"{ac.aircraft_model:<18} {ac.msn:<8} {mods_str:<30}"
        row_data = {
            "aircraft_model": ac.aircraft_model,
            "msn": ac.msn,
            "modifications": ac.modifications_applied,
        }
        for ad in ads:
            affected = is_affected(ac, ad)
            status = "✅ Affected" if affected else "❌ Not applicable"
            row += f" {status:<22}"
            row_data[ad.ad_id] = "Affected" if affected else "Not applicable"
        print(row)
        results_table.append(row_data)

    # Save results
    with open("test_results.json", "w") as f:
        json.dump(results_table, f, indent=2)
    print(f"\nResults saved to: test_results.json")

    # ── Step 3: Verification ──
    print("\n" + "=" * 70)
    print("STEP 3: VERIFICATION AGAINST EXPECTED RESULTS")
    print("=" * 70)

    all_pass = True
    for i, v in enumerate(VERIFICATION, 1):
        ac = v["aircraft"]
        expected = v["expected"]
        mods_str = ", ".join(ac.modifications_applied) if ac.modifications_applied else "None"
        print(f"\nVerification {i}: {ac.aircraft_model} MSN {ac.msn} ({mods_str})")

        for ad in ads:
            affected = is_affected(ac, ad)
            actual = "Affected" if affected else "Not applicable"

            # Try matching with both possible AD ID formats
            exp_val = None
            for key in expected:
                # Normalize both for comparison
                norm_key = key.replace("R1", "").replace("-", "")
                norm_ad = ad.ad_id.replace("R1", "").replace("-", "")
                if norm_key == norm_ad or key in ad.ad_id or ad.ad_id in key:
                    exp_val = key
                    break

            if exp_val:
                exp_result = expected[exp_val]
                # "Not affected" and "Not applicable" both mean not affected
                actual_norm = "not" if "not" in actual.lower() else "affected"
                exp_norm = "not" if "not" in exp_result.lower() else "affected"
                match = actual_norm == exp_norm
                status = "PASS ✅" if match else "FAIL ❌"
                if not match:
                    all_pass = False
                print(f"  {ad.ad_id}: {actual} (expected: {exp_result}) -> {status}")
            else:
                print(f"  {ad.ad_id}: {actual} (no expected value)")

    print(f"\n{'All verifications passed! ✅' if all_pass else 'Some verifications FAILED ❌'}")


if __name__ == "__main__":
    main()
