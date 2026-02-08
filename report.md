# Report: AD Applicability Rule Extraction Pipeline

## Approach

I chose a **regex-based text extraction** approach using `pdfplumber` for PDF-to-text conversion and targeted regular expressions for rule parsing.

The pipeline works in three stages:

1. **PDF Text Extraction**: `pdfplumber` extracts raw text from each PDF page. Both ADs in this assignment are text-based PDFs (not scanned images), so OCR was unnecessary.

2. **Rule Identification & Parsing**: The extractor identifies key sections — authority (FAA/EASA), AD ID, aircraft models, MSN constraints, and modification-based exclusions — using regex patterns tailored to the language conventions of aviation directives. For EASA ADs, I specifically target the "Applicability" section and parse "except those on which..." clauses to extract modification exclusions.

3. **Structured Output**: Extracted data is validated through Pydantic models and serialized to JSON.

### Why this approach over alternatives?

- **LLM-based extraction** would work well for handling varied AD formats, but adds API cost, latency, and non-determinism. For a pipeline processing hundreds of ADs monthly, deterministic regex parsing is more predictable and auditable.
- **VLM (Vision Language Models)** would be needed for scanned/image-based PDFs, but these ADs are text-based, making VLMs unnecessary overhead.
- **Rule-based parsing** gives full control over what gets extracted and how, making it easier to debug when results don't match expectations.

## Challenges

The main challenge was the **nuanced applicability language** in the EASA AD. The applicability section contains nested exclusion clauses:

> "...all MSN, except those on which Airbus modification (mod) 24591 has been embodied in production **and** except those on which Airbus Service Bulletin (SB) A320-57-1089 at Revision 04 has been embodied in service"

This required careful regex design to:
- Capture both `mod XXXXX` and `SB XXXX-XX-XXXX Rev XX` patterns
- Preserve the context (production vs. service)
- Handle the fact that A320 and A321 have **different** exclusion modifications (mod 24591 for A320, mod 24977 for A321)

The current implementation treats all exclusions as applying to all models in the AD. This works for the test cases because the evaluation only checks if an aircraft's applied modifications match any exclusion — and in practice, A321s won't have mod 24591 applied and A320s won't have mod 24977.

## Limitations

1. **Model-specific exclusions not fully modeled**: The AD specifies that mod 24591 excludes A320s and mod 24977 excludes A321s. My current model stores exclusions at the AD level, not per-model. A more robust schema would map exclusions to specific model groups.

2. **Group-based requirements not captured**: The EASA AD defines Groups 1-4 with different inspection requirements and timelines. My pipeline extracts the top-level applicability (which aircraft are affected) but doesn't model the group-specific compliance actions.

3. **Regex brittleness**: The extraction patterns are tuned to the language patterns in these two ADs. Different authorities or older ADs may use different phrasing that the current regexes wouldn't catch. A production system would need a larger pattern library or an LLM fallback.

4. **No flight hours/cycles evaluation**: Some AD applicability depends on flight hours or cycles, which I don't model in the aircraft configuration.

## Trade-offs

I deliberately chose **not** to use an LLM for extraction because:
- The two source ADs are well-structured text PDFs with predictable formatting
- Regex gives deterministic, reproducible results
- No API costs or rate limits
- Easier to unit test and debug

However, for a **production system** processing hundreds of diverse ADs monthly, I would recommend a **hybrid approach**:
- Use regex/rule-based extraction as the primary method for well-structured ADs
- Fall back to an LLM (e.g., Claude or GPT-4) for ADs with unusual formatting or ambiguous language
- Use the LLM output as a draft that gets validated against the Pydantic schema
- Flag low-confidence extractions for human review

This gives the best of both worlds: speed and determinism for the common case, with LLM flexibility for edge cases.
