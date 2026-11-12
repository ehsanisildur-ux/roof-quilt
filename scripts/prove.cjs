const fs = require('node:fs');
const path = require('node:path');
const {root, assert, equal, digest, sourceHash, invoke, read, rpc, receipt, receiptSummary, save} = require('./transport.cjs');
const {decodeReceipt} = require('./receipt-calldata.cjs');

const buildings = [1015862, 2019299];
const missing = 1999999;
const endpoint = bin => 'https://data.cityofnewyork.us/resource/5zhs-2jue.json?bin=' + bin + '&$limit=2';

async function city(bin) {
  const response = await fetch(endpoint(bin), {signal: AbortSignal.timeout(45000)});
  assert(response.ok, 'NYC source HTTP ' + response.status);
  return response.json();
}

function verifyGeometry(bin, plan, records) {
  assert(records.length === 1 && Number(records[0].bin) === bin, 'Expected one matching NYC footprint');
  const polygon = records[0].the_geom;
  assert(polygon.type === 'MultiPolygon' && polygon.coordinates.length === 1
    && polygon.coordinates[0].length === 1, 'Unexpected NYC geometry');
  const source = polygon.coordinates[0][0].map(point => point.map(n => Math.round(n * 1e12)));
  assert(equal(source[0], source.pop()), 'NYC ring is open');
  const start = source.findIndex(point => equal(point, plan.ring[0]));
  assert(start >= 0, 'Stored ring start missing from NYC data');
  const forward = source.slice(start).concat(source.slice(0, start));
  assert(equal(plan.ring, forward) || equal(plan.ring, [forward[0], ...forward.slice(1).reverse()]), 'Ring differs from NYC data');
  assert(plan.bin === bin && plan.grid === 8 && plan.scale === 1e12
    && plan.geometry_sha256 === digest(JSON.stringify(plan.ring)), 'Geometry metadata mismatch');
  const xs = source.map(p => p[0]);
  const ys = source.map(p => p[1]);
  const bbox = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  assert(equal(plan.bounds, bbox), 'Bounds differ from NYC data');
  const dx = BigInt(bbox[2] - bbox[0]), dy = BigInt(bbox[3] - bbox[1]);
  const ring = source.map(([x, y]) => [8n * BigInt(x - bbox[0]), 8n * BigInt(y - bbox[1])]);
  const segments = ring.map((point, i) => [point, ring[(i + 1) % ring.length]]);
  const side = (a, b, p) => (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
  const winding = point => segments.reduce((sum, [a, b]) => {
    const cross = side(a, b, point);
    if (a[1] <= point[1] && b[1] > point[1] && cross > 0n) return sum + 1;
    if (a[1] > point[1] && b[1] <= point[1] && cross < 0n) return sum - 1;
    return sum;
  }, 0);
  // A segment is separated from a box along x, y, or the segment's normal.
  const insideCell = (x, y) => {
    const l = BigInt(x) * dx, r = l + dx, b = BigInt(y) * dy, t = b + dy;
    const corners = [[l, b], [r, b], [r, t], [l, t]];
    return winding(corners[0]) !== 0 && segments.every(([p, q]) => {
      if ((p[0] < l && q[0] < l) || (p[0] > r && q[0] > r)
        || (p[1] < b && q[1] < b) || (p[1] > t && q[1] > t)) return true;
      const distances = corners.map(corner => side(p, q, corner));
      return distances.every(d => d > 0n) || distances.every(d => d < 0n);
    });
  };
  const raster = Array.from({length: 8}, (_, y) =>
    Array.from({length: 8}, (_, x) => insideCell(x, y) ? '1' : '0').join(''));
  assert(equal(plan.interior, raster), 'Raster differs from independent winding/axis test');
  return raster;
}

function verifyTiles(plan, raster) {
  const target = new Set();
  for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) if (raster[r][c] === '1') target.add(r * 8 + c);
  const seen = new Set();
  let perimeter = 0;
  for (const {row, column, height, width} of plan.tiles) {
    assert([row, column, height, width].every(Number.isInteger)
      && row >= 0 && column >= 0 && height > 0 && width > 0
      && row + height <= 8 && column + width <= 8, 'Tile bounds');
    for (let r = row; r < row + height; r++) for (let c = column; c < column + width; c++) {
      const cell = r * 8 + c;
      assert(target.has(cell) && !seen.has(cell), 'Tile covers outside or overlaps');
      seen.add(cell);
    }
    perimeter += 2 * (width + height);
  }
  assert(seen.size === target.size && plan.cell_count === seen.size
    && plan.tiles.length === plan.tile_count && perimeter === plan.tile_perimeter, 'Tile totals');

  const costs = new Map();
  // Encode the two objectives as one cost. All 64 unit tiles cost only 256 in perimeter.
  for (let height = 1; height <= 8; height++) for (let width = 1; width <= 8; width++) {
    for (let r = 0; r + height <= 8; r++) for (let c = 0; c + width <= 8; c++) {
      let fill = 0;
      for (let y = r; y < r + height; y++) for (let x = c; x < c + width; x++) fill += target.has(y * 8 + x);
      let cost = fill === 0 ? 0 : fill === height * width ? 257 + 2 * (height + width) : Infinity;
      for (let y = 1; y < height; y++) cost = Math.min(cost, costs.get([r,c,y,width].join()) + costs.get([r+y,c,height-y,width].join()));
      for (let x = 1; x < width; x++) cost = Math.min(cost, costs.get([r,c,height,x].join()) + costs.get([r,c+x,height,width-x].join()));
      costs.set([r,c,height,width].join(), cost);
    }
  }
  assert(costs.get('0,0,8,8') === 257 * plan.tile_count + perimeter, 'Nonoptimal guillotine partition');
}

async function main() {
  const scenario = process.env.QUILT_SCENARIO;
  assert(['plans', 'rejection'].includes(scenario), 'Choose a proof scenario');
  const wallets = JSON.parse(process.env.QUILT_ACCOUNTS || '[]');
  assert(wallets.length === 2 && wallets[0].address !== wallets[1].address, 'Two distinct wallets required');
  const prefix = scenario + '-';
  const code = fs.readFileSync(path.join(root, 'contracts/roof_quilt.py'));
  const refs = new Map();
  for (const bin of scenario === 'plans' ? buildings : [missing]) refs.set(bin, await city(bin));
  assert(await rpc('eth_chainId', []) === '0xf22f', 'StudioNet only');

  process.env.QUILT_ACCOUNT = wallets[0].name;
  const deployment = await invoke(prefix + 'deploy', ['deploy', '--contract', 'contracts/roof_quilt.py']);
  const deployed = await receipt(prefix + 'deploy', deployment, true);
  const contract = deployed.to_address || deployed.recipient;
  assert(/^0x[0-9a-f]{40}$/i.test(contract), 'Missing deployed contract');
  assert(code.equals(Buffer.from(deployed.data.contract_code, 'base64')), 'Deployment source mismatch');
  const report = {scenario, contract, deployment, source_sha256: sourceHash, revision: process.env.GITHUB_SHA, trace: [], plans: {}};

  async function verify(label, raw, actor, args, error) {
    assert((raw.from_address || raw.sender).toLowerCase() === wallets[actor].address, 'Wrong sender');
    assert((raw.to_address || raw.recipient).toLowerCase() === contract.toLowerCase(), 'Wrong recipient');
    assert(equal(await decodeReceipt(raw), args), 'Unexpected signed calldata');
    if (error) {
      const payload = Buffer.from(raw.consensus_data.leader_receipt[0].result, 'base64');
      assert(payload[0] === 1 && payload.subarray(1).toString() === error, 'Wrong revert reason');
    }
    const count = await read(prefix + label + '-count', ['call', contract, 'get_count']);
    assert(count.plans === Object.keys(report.plans).length, 'Unexpected plan count');
    for (const bin of refs.keys()) {
      const state = await read(prefix + label + '-bin-' + bin, ['call', contract, 'get_plan', '--args', String(bin)]);
      assert(equal(state, report.plans[bin] || {}), 'Unexpected plan state for ' + bin);
    }
    report.trace.push({label, ...receiptSummary(raw), signer: wallets[actor].address, args, error: error || null, count});
    save(prefix + 'progress', report);
  }
  await verify('deploy', deployed, 0, {args: []});

  async function write(label, bin, actor, error) {
    process.env.QUILT_ACCOUNT = wallets[actor].name;
    const tx = await invoke(prefix + label, ['write', contract, 'plan', '--args', String(bin)]);
    const raw = await receipt(prefix + label, tx, !error);
    if (!error) {
      const plan = await read(prefix + label + '-new-plan', ['call', contract, 'get_plan', '--args', String(bin)]);
      verifyTiles(plan, verifyGeometry(bin, plan, refs.get(bin)));
      report.plans[bin] = plan;
    }
    await verify(label, raw, actor, {method: 'plan', args: [bin]}, error);
  }

  if (scenario === 'plans') {
    await write('empire-state', buildings[0], 1);
    await write('bronx-footprint', buildings[1], 0);
    assert(!equal(report.plans[buildings[0]].interior, report.plans[buildings[1]].interior), 'Expected distinct plans');
    await write('duplicate', buildings[0], 0, 'Footprint already planned');
  } else {
    assert(refs.get(missing).length === 0, 'Missing BIN must be absent in NYC data');
    await write('missing', missing, 1, 'No unique building footprint');
    await write('invalid', 2000000, 0, 'Invalid building identifier');
  }
  assert(code.equals(Buffer.from(await rpc('gen_getContractCode', [contract]), 'base64')), 'Fresh code mismatch');
  save(prefix + 'verified', report);
  console.log(JSON.stringify({scenario, contract, deployment, receipts: report.trace.length,
    plans: Object.values(report.plans).map(({bin, cell_count, tile_count}) => ({bin, cell_count, tile_count}))}));
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
module.exports = {verifyGeometry, verifyTiles};
