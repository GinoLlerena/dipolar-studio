# dipolar-core

The pure scientific core of Dipolar Studio: molecule model, Cartesian forward model, nuclide
table and the D3 inference stack. **No I/O, no global state, no UI, no web framework.** Every
client (the application layer, notebooks, the browser and, later, an AI agent) reaches it
through `dipolar-app`. The boundary is enforced by `tests/test_boundaries.py`.
