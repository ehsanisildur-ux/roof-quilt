import json
from pathlib import Path
import re

import pytest


BIN = 1015862
URL = 'https://data.cityofnewyork.us/resource/5zhs-2jue.json?bin={}&$limit=2'
SQUARE = [[0, 0], ['0.008', 0], ['0.008', '0.008'], [0, '0.008'], [0, 0]]


def deploy(direct_deploy):
    return direct_deploy('contracts/roof_quilt.py', sdk_version='v0.2.16')


def footprint(ring, building=BIN):
    return [{'bin': str(building), 'the_geom': {'type': 'MultiPolygon', 'coordinates': [[ring]]}}]


def reply(vm, value, building=BIN, status=200):
    vm.clear_mocks()
    body = value if isinstance(value, bytes) else json.dumps(value).encode()
    vm.mock_web(re.escape(URL.format(building)), {'status': status, 'body': body})


def check_tiles(plan):
    cells = set()
    perimeter = 0
    for tile in plan['tiles']:
        r, c, h, w = (tile[key] for key in ('row', 'column', 'height', 'width'))
        assert h > 0 and w > 0 and r + h <= 8 and c + w <= 8
        rectangle = {(i, j) for i in range(r, r + h) for j in range(c, c + w)}
        assert not cells.intersection(rectangle)
        cells.update(rectangle)
        perimeter += 2 * (w + h)
    expected = {(i, j) for i, row in enumerate(plan['interior']) for j, bit in enumerate(row) if bit == '1'}
    assert cells == expected
    assert plan['cell_count'] == len(expected)
    assert plan['tile_count'] == len(plan['tiles'])
    assert plan['tile_perimeter'] == perimeter


def test_strict_boundary_and_minimum_rectangle(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    reply(direct_vm, footprint(SQUARE))
    contract.plan(BIN)
    assert direct_vm.run_validator() is True
    plan = contract.get_plan(BIN)
    assert plan['bounds'] == [0, 0, 8_000_000_000, 8_000_000_000]
    assert plan['interior'] == ['00000000'] + ['01111110'] * 6 + ['00000000']
    assert plan['tiles'] == [{'row': 1, 'column': 1, 'height': 6, 'width': 6}]
    check_tiles(plan)
    with direct_vm.expect_revert('Footprint already planned'):
        contract.plan(BIN)
    assert contract.get_plan(BIN) == plan
    assert contract.get_count() == {'plans': 1}


def test_validator_equivalence_requires_full_geometry(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    reply(direct_vm, footprint(SQUARE))
    contract.plan(BIN)
    rotated = list(reversed(SQUARE[1:4] + SQUARE[:1]))
    reply(direct_vm, footprint(rotated + [rotated[0]]))
    assert direct_vm.run_validator() is True
    wider = [[0, 0], ['0.009', 0], ['0.009', '0.008'], [0, '0.008'], [0, 0]]
    reply(direct_vm, footprint(wider))
    assert direct_vm.run_validator() is False


def test_narrow_notch_enters_cell_between_its_corners(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    ring = SQUARE[:3] + [['0.0048', '0.008'], ['0.0048', '0.0035'],
                         ['0.0042', '0.0035'], ['0.0042', '0.008']] + SQUARE[3:]
    reply(direct_vm, footprint(ring))
    contract.plan(BIN)
    plan = contract.get_plan(BIN)
    assert plan['interior'][2][4] == '1'
    assert plan['interior'][3][4] == '0'
    assert plan['tile_count'] > 1
    check_tiles(plan)


def test_real_city_footprint(direct_vm, direct_deploy):
    contract = deploy(direct_deploy)
    reply(direct_vm, Path('fixtures/1015862.json').read_bytes())
    contract.plan(BIN)
    assert direct_vm.run_validator() is True
    plan = contract.get_plan(BIN)
    assert len(plan['ring']) == 14
    assert 0 < plan['cell_count'] < 64
    check_tiles(plan)


@pytest.mark.parametrize(('value', 'status', 'reason'), [
    ([], 200, 'No unique building footprint'),
    (footprint(SQUARE) * 2, 200, 'No unique building footprint'),
    (footprint(SQUARE, BIN + 1), 200, 'Footprint identifier mismatch'),
    (footprint(SQUARE[:-1]), 200, 'Footprint is not closed'),
    (footprint([[0, 0], ['0.008', '0.008'], ['0.006', 0], [0, '0.007'], [0, 0]]), 200,
     'Footprint self-intersects'),
    (footprint([[0, 0], ['0.0080000000001', 0], *SQUARE[2:]]), 200, 'Unsupported coordinate precision'),
    (b'[{"bin":"1015862","bin":"1015862"}]', 200, 'Invalid footprint JSON'),
    (b'unavailable', 503, 'Footprint source unavailable'),
])
def test_rejection_leaves_slot_open(direct_vm, direct_deploy, value, status, reason):
    contract = deploy(direct_deploy)
    reply(direct_vm, value, status=status)
    with direct_vm.expect_revert(reason):
        contract.plan(BIN)
    assert contract.get_plan(BIN) == {}
    assert contract.get_count() == {'plans': 0}
    reply(direct_vm, footprint(SQUARE))
    contract.plan(BIN)
    assert contract.get_count() == {'plans': 1}


@pytest.mark.parametrize('building', [999999, 2000000, 6000000])
def test_invalid_identifier(direct_vm, direct_deploy, building):
    contract = deploy(direct_deploy)
    with direct_vm.expect_revert('Invalid building identifier'):
        contract.plan(building)
    assert contract.get_count() == {'plans': 0}
