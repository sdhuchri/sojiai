# AD Applicability Rule Extraction Pipeline

Automated pipeline that extracts applicability rules from Airworthiness Directive (AD) PDFs, structures them as machine-readable JSON, and evaluates whether specific aircraft configurations are affected.

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

This will:
1. Extract rules from all `*.pdf` files in the current directory
2. Save structured output to `extracted_rules.json`
3. Evaluate 10 test aircraft configurations against both ADs
4. Run 3 verification checks against expected results
5. Save evaluation results to `test_results.json`

## Project Structure

```
├── models.py          # Pydantic data models (AD, rules, aircraft config)
├── extractor.py       # PDF text extraction + rule parsing pipeline
├── evaluator.py       # Aircraft-vs-AD evaluation logic
├── main.py            # Main runner: extract → evaluate → verify
├── requirements.txt   # Python dependencies
├── report.md          # Written analysis report
└── *.pdf              # Source AD documents
```

## Usage

### Extract from specific PDFs
```bash
python extractor.py path/to/ad1.pdf path/to/ad2.pdf
```

### Evaluate a custom aircraft
```python
from models import AircraftConfig
from extractor import extract_from_pdf
from evaluator import is_affected

ad = extract_from_pdf("EASA_AD_2025-0254R1_1.pdf")
aircraft = AircraftConfig(
    aircraft_model="A320-214",
    msn=5000,
    modifications_applied=["mod 24591"]
)
print(is_affected(aircraft, ad))  # False — excluded by mod
```

## Dependencies

- Python 3.10+
- pdfplumber (PDF text extraction)
- pydantic (data validation/serialization)
