// GENERATED FILE: do not edit. Regenerate with `uv run python tools/codegen/ts_contract.py`.
// Type-level conformance: each registry example satisfies its operation's input type.
// Checked by `tsc`; nothing imports this file, so it is not bundled.

import type { OperationInput } from "./contract";

void ({"confirmed_mapping": {"H2": "spn_000001", "H3": "spn_000002"}, "csv": "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\n", "expected_science_revision": 1} satisfies OperationInput<"couplings.import">); // example 0
void ({"csv": "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\n"} satisfies OperationInput<"couplings.reconcile">); // example 0
void ({"phi": {"unit": "deg", "value": 37.0}} satisfies OperationInput<"fit.preview">); // example 0
void ({"expected_science_revision": 1} satisfies OperationInput<"fit.run">); // example 0
void ({"expected_science_revision": 1, "intervals": true} satisfies OperationInput<"fit.run">); // example 1
void ({} satisfies OperationInput<"history.log">); // example 0
void ({"expected_science_revision": 2} satisfies OperationInput<"history.redo">); // example 0
void ({"expected_science_revision": 2} satisfies OperationInput<"history.undo">); // example 0
void ({"job_id": "job_000001"} satisfies OperationInput<"job.cancel">); // example 0
void ({} satisfies OperationInput<"job.list">); // example 0
void ({"status": "unfinished"} satisfies OperationInput<"job.list">); // example 1
void ({"job_id": "job_000001"} satisfies OperationInput<"job.status">); // example 0
void ({"job_id": "job_000001", "timeout_s": 5.0} satisfies OperationInput<"job.wait">); // example 0
void ({"expected_science_revision": 1, "frame": "bisector", "kind": "jump4", "order": "bisector-diagonal", "phi_domain": [{"unit": "deg", "value": 0.0}, {"unit": "deg", "value": 90.0}]} satisfies OperationInput<"model.set">); // example 0
void ({"expected_science_revision": 1, "torsion": [3, 0, 1, 6]} satisfies OperationInput<"molecule.set_torsion">); // example 0
void ({} satisfies OperationInput<"project.describe">); // example 0
void ({} satisfies OperationInput<"project.export">); // example 0
void ({"expected_science_revision": 0, "name": "ethane", "torsion": [2, 0, 1, 5], "xyz": "8\nethane, staggered\nC 0 0 0\nC 1.54 0 0\nH -0.36 1.03 0\nH -0.36 -0.515 0.892\nH -0.36 -0.515 -0.892\nH 1.9 -1.03 0\nH 1.9 0.515 0.892\nH 1.9 0.515 -0.892\n"} satisfies OperationInput<"project.import_xyz">); // example 0
void ({"expected_science_revision": 0, "text": "{\n  \"format\": \"dipolar-studio-project\",\n  \"project\": {\n    \"couplings\": [],\n    \"model\": {\n      \"frame\": \"input\",\n      \"kind\": \"rigid\",\n      \"order\": \"c1\",\n      \"phi_domain_deg\": [\n        -180.0,\n        180.0\n      ]\n    },\n    \"molecule\": {\n      \"geometry\": {\n        \"atoms\": [\n          {\n            \"element\": \"C\",\n            \"x\": 0.0,\n            \"y\": 0.0,\n            \"z\": 0.0\n          },\n          {\n            \"element\": \"C\",\n            \"x\": 1.54,\n            \"y\": 0.0,\n            \"z\": 0.0\n          },\n          {\n            \"element\": \"H\",\n            \"x\": -0.36,\n            \"y\": 1.03,\n            \"z\": 0.0\n          },\n          {\n            \"element\": \"H\",\n            \"x\": -0.36,\n            \"y\": -0.515,\n            \"z\": 0.892\n          },\n          {\n            \"element\": \"H\",\n            \"x\": -0.36,\n            \"y\": -0.515,\n            \"z\": -0.892\n          },\n          {\n            \"element\": \"H\",\n            \"x\": 1.9,\n            \"y\": -1.03,\n            \"z\": 0.0\n          },\n          {\n            \"element\": \"H\",\n            \"x\": 1.9,\n            \"y\": 0.515,\n            \"z\": 0.892\n          },\n          {\n            \"element\": \"H\",\n            \"x\": 1.9,\n            \"y\": 0.515,\n            \"z\": -0.892\n          }\n        ],\n        \"source_format\": \"xyz\",\n        \"torsion\": [\n          2,\n          0,\n          1,\n          5\n        ]\n      },\n      \"spins\": [\n        {\n          \"atom\": 2,\n          \"id\": \"spn_000001\",\n          \"isotope\": \"1H\",\n          \"label\": \"H3\"\n        },\n        {\n          \"atom\": 3,\n          \"id\": \"spn_000002\",\n          \"isotope\": \"1H\",\n          \"label\": \"H4\"\n        },\n        {\n          \"atom\": 4,\n          \"id\": \"spn_000003\",\n          \"isotope\": \"1H\",\n          \"label\": \"H5\"\n        },\n        {\n          \"atom\": 5,\n          \"id\": \"spn_000004\",\n          \"isotope\": \"1H\",\n          \"label\": \"H6\"\n        },\n        {\n          \"atom\": 6,\n          \"id\": \"spn_000005\",\n          \"isotope\": \"1H\",\n          \"label\": \"H7\"\n        },\n        {\n          \"atom\": 7,\n          \"id\": \"spn_000006\",\n          \"isotope\": \"1H\",\n          \"label\": \"H8\"\n        }\n      ]\n    },\n    \"name\": \"ethane\",\n    \"next_coupling_id\": 1,\n    \"schema_version\": 2,\n    \"source\": \"registry example\"\n  },\n  \"schema_version\": 2\n}\n"} satisfies OperationInput<"project.load">); // example 0
void ({"expected_science_revision": 0, "name": "biphenyl-synthetic"} satisfies OperationInput<"project.open_example">); // example 0
void ({"proposal_id": "prp_000001"} satisfies OperationInput<"proposal.accept">); // example 0
void ({"proposal_id": "prp_000001", "steps": [0]} satisfies OperationInput<"proposal.accept">); // example 1
void ({"note": "try the four-site jump model", "steps": [{"args": {"expected_science_revision": 1, "frame": "bisector", "kind": "jump4", "order": "bisector-diagonal", "phi_domain": [{"unit": "deg", "value": 0.0}, {"unit": "deg", "value": 90.0}]}, "operation": "model.set"}]} satisfies OperationInput<"proposal.create">); // example 0
void ({"proposal_id": "prp_000001"} satisfies OperationInput<"proposal.get">); // example 0
void ({} satisfies OperationInput<"proposal.list">); // example 0
void ({"status": "pending"} satisfies OperationInput<"proposal.list">); // example 1
void ({"proposal_id": "prp_000001", "reason": "keep the bisector-diagonal model"} satisfies OperationInput<"proposal.reject">); // example 0
void ({} satisfies OperationInput<"render.describe_view">); // example 0
void ({"run_id": "run_000001"} satisfies OperationInput<"run.get">); // example 0
void ({} satisfies OperationInput<"run.list">); // example 0
void ({"ids": ["cpl_000002"]} satisfies OperationInput<"view.select">); // example 0
