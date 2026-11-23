# Verification: biphenyl in 8CB (Di Pietro 2013)

**Verification:** `pending`

Pending: matching the thesis's AP-DPD model needs a torsional-distribution model, which is
deferred.

| Field | Entry |
|---|---|
| Source and channel | M. E. Di Pietro, PhD thesis, Université Paris-Sud / Università della Calabria (2013), Chapter 3: Table 3.1 (the experimental couplings) and Table 3.2 (the AP-DPD results). The couplings and their provenance are in [the dataset README](../../../datasets/biphenyl-8CB-dipietro2013/README.md), with that README's licence terms: validation only. The beta ships no 8CB couplings. |
| Role | Development and regression data. It is not the untouched holdout. |
| Model and estimand | Rigid rings with the symmetric four-site jump average. Its estimand is an **effective** torsion, not the mode φ_m of the thesis's Gaussian torsional distribution (AP-DPD). The two are different estimands. |
| Project result | The frozen four-site-jump regression at T_red 0.930 and 0.980, under the Phase 1 tolerances ([`expected/`](../../../datasets/biphenyl-8CB-dipietro2013/expected/)). |
| Reference and criterion | The thesis's AP-DPD comparison is pending. The order parameters agree descriptively (README); that is not independent validation of either model. Under the printed spectral σ the rigid jump model is grossly inadequate, and the engine reports it so, without rescaling σ. |
| Distribution model | Deferred (a post-beta gate). |
| Beta exercise | [`docs/beta/testers.md`](../../beta/testers.md): reproduce biphenyl in 8CB from your own transcription. |
| Robot tutorial | The four-site-jump model's tutorial, `robot.py --scenario jump4-tutorial`, runs on synthetic couplings with a known answer ([`jump4_tutorial.py`](../../../datasets/biphenyl-synthetic/jump4_tutorial.py)), not on the 8CB data. An agent proposes the jump model and a fit, a human accepts, and the robot reports the complete run. Gate: [`test_app_v15_jump4.py`](../../../packages/dipolar-app/tests/test_app_v15_jump4.py). |
| Gate evidence | `tests/test_m1_acceptance.py`, `tests/test_expected_fixtures.py`, `web/e2e/eightcb.spec.ts`. |
