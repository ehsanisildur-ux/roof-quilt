# StudioNet proofs

Both instances used the same contract source. GenVM lint, 15 direct tests and 7 CLI transport tests passed. All seven receipts finalized with MAJORITY_AGREE. The rejection rows record expected contract errors.

Source revision: d3ad48d387bf129150f198e45485b0d496fbe51f

Source SHA-256: 6cfa2f433c704d65bdc481db9628bff25e08e3ad01e679877add2e25783818a2

## Two real footprints and duplicate protection

Contract address: 0x5477651cFE75009964AAD4a5Bf332F8Ae2a6e24A

[Workflow](https://github.com/ehsanisildur-ux/roof-quilt/actions/runs/43751170597) · [State verification](plans-verified.json)

| Outcome | Explorer | Receipt | Agree / disagree / idle |
| --- | --- | --- | --- |
| Contract deployed | [Transaction](https://explorer-studio.genlayer.com/tx/0x55a2e11d6a449e1f625637fd2965e5b1721f067a4b5816988cb62bb72572fb64) | [JSON](plans-deploy-receipt.json) | 3 / 0 / 2 |
| Empire State Building, 15 cells and 5 tiles | [Transaction](https://explorer-studio.genlayer.com/tx/0xcebc2283c0caed2208952476a6de430eef436f1211bf1487370f14d848f0475b) | [JSON](plans-empire-state-receipt.json) | 3 / 0 / 2 |
| Bronx footprint, 29 cells and 3 tiles | [Transaction](https://explorer-studio.genlayer.com/tx/0x8fa4bc49a1cfc7c0477eb9f422b81b57b5008b39ffafc2525fbb5e042887c17f) | [JSON](plans-bronx-footprint-receipt.json) | 3 / 0 / 2 |
| Duplicate BIN rejected, both plans retained | [Transaction](https://explorer-studio.genlayer.com/tx/0xf794f96410c1b1f8009e61f3ee65381582a2ee700186416024c01891f4950904) | [JSON](plans-duplicate-receipt.json) | 3 / 0 / 2 |

## Missing footprint and invalid identifier

Contract address: 0x168F32Ae6C6B05AAaBCEd1A0a0e0dd00f0FD1D8e

[Workflow](https://github.com/ehsanisildur-ux/roof-quilt/actions/runs/43751178075) · [State verification](rejection-verified.json)

| Outcome | Explorer | Receipt | Agree / disagree / idle |
| --- | --- | --- | --- |
| Contract deployed | [Transaction](https://explorer-studio.genlayer.com/tx/0xa4cf375060a1b3c184db48e503b8e40dadc0169391683395e2ba5a0952998c86) | [JSON](rejection-deploy-receipt.json) | 4 / 0 / 1 |
| Missing city footprint rejected, zero plans | [Transaction](https://explorer-studio.genlayer.com/tx/0xef6f4441226f785186bad87853b12e6a0893a2ddc7602568ffdd2d035b1f9eda) | [JSON](rejection-missing-receipt.json) | 3 / 0 / 2 |
| Invalid BIN rejected, zero plans | [Transaction](https://explorer-studio.genlayer.com/tx/0x99902e99894220f4b8b58576a7c60f715e0f7c518319d54393189c3ddec57000) | [JSON](rejection-invalid-receipt.json) | 3 / 0 / 2 |

The proof script compared the onchain polygons with a separate NYC Open Data request. It checked every grid cell, exact tile coverage, minimum guillotine cost, signed calldata, deployed bytes, and state after each transaction.
