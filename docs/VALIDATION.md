# Validation boundaries

## Existing public history and new privacy checks

The public main ancestry already includes author/committer metadata that the generic checker flags. Rewriting published history would break ancestry and existing pins. `scripts/generic-history-baseline.json` records only exact commit IDs, metadata field names and SHA-256 hashes from the pinned public revision. It contains no copied personal metadata. The checker still reports its baseline count, scans every source file and commit message, and rejects changed/new commits, changed metadata, other fields and local denied terms. A malformed or unreachable baseline fails closed. Regression fixtures exercise those boundaries without altering public history.

## Viewport contract

Viewport inputs must be two positive integer dimensions. Lists, tuples and the omitted default are accepted. Numeric strings, booleans and floats are deliberately rejected rather than silently coerced. Parser failures retain a location-specific typed error; invalid mutated objects return a failed validation report. Boundary tests do not establish recording, rendering, provider or outside-user outcomes.
