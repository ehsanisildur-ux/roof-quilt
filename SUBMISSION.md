# RoofQuilt — Consensus building footprint partitioner

**Category** Builder → Intelligent Contracts

**Description**

RoofQuilt turns a NYC Building Identification Number into an immutable rectangular coverage plan. The GenLayer leader and validators independently fetch the city footprint, normalize the full polygon, and compute which cells of an 8 × 8 grid lie strictly inside it. They require exact agreement on the polygon, grid and tile layout. A dynamic program finds the fewest tiles obtainable by recursive straight cuts, then minimizes their total grid perimeter. StudioNet proofs verified the Empire State Building (15 cells, 5 tiles) and a Bronx building (29 cells, 3 tiles). Duplicate, missing and invalid IDs were rejected. All seven receipts finalized with MAJORITY_AGREE. The repo includes 15 direct tests. Plans model coarse, single-ring building footprints.

**Evidence**

- [GenLayer contract source](contracts/roof_quilt.py)
- [StudioNet deployment](https://explorer-studio.genlayer.com/tx/0x55a2e11d6a449e1f625637fd2965e5b1721f067a4b5816988cb62bb72572fb64)
- [Seven StudioNet receipts and verification](proofs/README.md)
