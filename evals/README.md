# Offline evaluations

`python -m evals.run --suite golden --mode structured` runs the sanitized,
recorded Phase 8 pipeline cases without a network request or API key.

Each case has a brief, fixed regional context, recorded structured extraction,
and approved expected pipeline projection. These fixtures are prototype-only;
they are not client proposals or training data. Add approved sanitized cases
as pricing, proposal, and rendering phases are implemented.
