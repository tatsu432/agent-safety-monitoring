# Dataset audit

Real source measurements; no monitor effectiveness results.

| Quantity | Count |
|---|---:|
| attack/failure | 18 |
| attack/success | 569 |
| attack/ungraded | 13 |
| benign/not_applicable | 600 |
| calibration/benign | 448 |
| development/attack | 120 |
| development/benign | 30 |
| excluded/attack | 8 |
| excluded/benign | 4 |
| test/attack | 472 |
| test/benign | 118 |
| Test successful attacks, usable | 454 |

Eight records have no usable tool behavior. Four additional attacks lack a usable
benign counterpart. Counts are before physical backend context validation.

Full source URLs and SHA-256 checksums are in the ignored raw source manifest.
The current normalized-source token counts omit chat-format/instruction overhead;
the complete-prompt context audit is a separate artifact.

| Class | Length measure | Median | Maximum | Median tool calls |
|---|---|---:|---:|---:|
| benign | source_tokens | 17837 | 99285 | 24 |
| attack | source_tokens | 14959 | 52522 | 13 |
