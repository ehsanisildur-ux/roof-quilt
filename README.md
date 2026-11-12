# RoofQuilt

RoofQuilt is a standalone GenLayer contract that turns a New York City Building Identification Number (BIN) into an immutable rectangular coverage plan. It provides a reproducible geometry primitive for builders who need a coarse footprint mask and a compact set of rectangular grid regions.

## Contract interface

| Method | Behavior |
| --- | --- |
| `plan(building)` | Anyone can request the first plan for a BIN. The contract fetches the footprint and stores the agreed plan. |
| `get_plan(building)` | Returns the normalized ring, geometry digest, bounds, cell mask, and tile layout. An unplanned BIN returns an empty object. |
| `get_count()` | Returns the number of stored plans. |

There is no constructor argument. A rejected call leaves the BIN available. A completed plan is an immutable snapshot, so a future change in the city dataset does not overwrite it.

## Consensus and geometry

The caller supplies only a numeric BIN. Inside `gl.vm.run_nondet_unsafe`, the leader fetches the city's Building Footprints API. Each validator independently fetches the same endpoint, normalizes the ring, rasterizes it, and solves the partition. Validators require exact equality of the normalized coordinates, mask and tile layout. They can agree on an identical contract error for an invalid response, such as a missing footprint. A source edit that changes the normalized ring makes the leader and validator disagree even if the mask remains the same.

The accepted GeoJSON subset is one closed exterior ring from a single MultiPolygon record, with 3–64 distinct vertices. Coordinates are integers in trillionths of a degree. The contract rejects degenerate, repeated or intersecting edges and checks bounds. It normalizes vertex start and direction so equivalent GeoJSON encodings produce the same plan.

Rows run south to north and columns west to east in an 8 × 8 grid across the bounding box. A cell counts only when its entire closed box is strictly inside the footprint. Even a narrow notch between corners excludes a cell. Subrectangle dynamic programming considers each straight horizontal and vertical cut. It minimizes tile count, then total grid perimeter, then lexicographic tile order. Tile count is optimal over **guillotine partitions**, where each cut crosses its current subrectangle. Tile coordinates are grid indices. The geometry represents a public building footprint snapshot and the plan measures grid coverage.

## Verification

```sh
python -m pip install -r requirements-dev.txt
genvm-lint download --version v0.2.16
genvm-lint check contracts/roof_quilt.py
python -m pytest tests/direct -q
npm ci
node --test tests/rpc-preflight.test.cjs
```

The StudioNet workflow uses the pinned GenLayer CLI, two disposable wallets, and independent BigInt winding and separating-axis checks. The proof script verifies the normalized onchain ring against a separate city API read, computes the minimum cut cost, checks signed calldata, and reads fresh contract state after each finalized receipt.

Test fixtures come from NYC Open Data, dataset `5zhs-2jue`. [City dataset](https://data.cityofnewyork.us/City-Government/BUILDING/5zhs-2jue/about_data) · [Empire State Building API record](https://data.cityofnewyork.us/resource/5zhs-2jue.json?bin=1015862&%24limit=2) · [Bronx API record](https://data.cityofnewyork.us/resource/5zhs-2jue.json?bin=2019299&%24limit=2).

CLI receipt transport is reused under the MIT license. The footprint normalizer, raster, optimizer, contract state and geometry verifier are specific to RoofQuilt.
