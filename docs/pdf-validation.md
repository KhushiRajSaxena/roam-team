# PDF export validation

September 14, 2026

The user-facing download action now saves a PDF instead of JSON. Export is browser-local and uses the completed plan, with no additional provider or model calls.

Checks completed:
- Generated a four-night sample plan (4 PDF pages) and a fourteen-night plan (6 PDF pages).
- Rendered and visually inspected all four pages of the sample: readable tables, no clipping or overlapping, repeated day headings across pages, consistent headers and page numbers.
- Extracted long-plan text and verified all 15 itinerary days are present.
- Tested incomplete plans, missing flights, long notes, and accented names (São Paulo and Zürich).
- Verified the .pdf filename, success status, and recoverable failure state in jsdom.
- Verified the actual rendered plan's Download PDF button passes that completed plan to the exporter.
- Confirmed the running app serves the new PDF exporter.

A native browser download-dialog interaction was not automated. The generator produced real PDFs, and the click handler/save call was checked with jsdom. No real travel API or model requests were used in these checks.
