# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from hashlib import sha256
import json
import re


API = 'https://data.cityofnewyork.us/resource/5zhs-2jue.json?bin={}&$limit=2'
GRID = 8
SCALE = 10**12


def fail(message):
    raise gl.vm.UserError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate JSON key')
        obj[key] = value
    return obj


def coordinate(value, limit):
    if type(value) is not int and not isinstance(value, str):
        fail('Unsupported coordinate')
    match = re.fullmatch(r'(-?)([0-9]{1,3})(?:\.([0-9]{1,12}))?', str(value))
    if match is None:
        fail('Unsupported coordinate precision')
    sign, whole, fraction = match.groups()
    magnitude = int(whole) * SCALE + int((fraction or '').ljust(12, '0'))
    if magnitude > limit * SCALE:
        fail('Coordinate outside geographic bounds')
    return -magnitude if sign else magnitude


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a, b, p):
    return (cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def intersects(a, b, c, d):
    ab_c, ab_d = cross(a, b, c), cross(a, b, d)
    cd_a, cd_b = cross(c, d, a), cross(c, d, b)
    if ab_c * ab_d < 0 and cd_a * cd_b < 0:
        return True
    return on_segment(a, b, c) or on_segment(a, b, d) or on_segment(c, d, a) or on_segment(c, d, b)


def edges(ring):
    return list(zip(ring, ring[1:] + ring[:1]))


def validate_ring(ring):
    if len(set(ring)) != len(ring):
        fail('Footprint repeats a vertex')
    sides = edges(ring)
    if sum(a[0] * b[1] - a[1] * b[0] for a, b in sides) == 0:
        fail('Footprint has zero area')
    for i, (a, b) in enumerate(sides):
        c = ring[(i + 2) % len(ring)]
        if cross(a, b, c) == 0 and (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) <= 0:
            fail('Footprint doubles back')
        for j in range(i + 2, len(sides)):
            if i == 0 and j == len(sides) - 1:
                continue
            if intersects(a, b, *sides[j]):
                fail('Footprint self-intersects')


def inside(point, sides):
    result = False
    for a, b in sides:
        if on_segment(a, b, point):
            return False
        if (a[1] > point[1]) != (b[1] > point[1]) and (cross(a, b, point) > 0) == (b[1] > a[1]):
            result = not result
    return result


def interior_cell(left, bottom, right, top, sides):
    corners = [(left, bottom), (right, bottom), (right, top), (left, top)]
    if not all(inside(corner, sides) for corner in corners):
        return False
    perimeter = edges(corners)
    for a, b in sides:
        if left <= a[0] <= right and bottom <= a[1] <= top:
            return False
        if any(intersects(a, b, c, d) for c, d in perimeter):
            return False
    return True


def raster(ring):
    min_x = min(x for x, _ in ring)
    max_x = max(x for x, _ in ring)
    min_y = min(y for _, y in ring)
    max_y = max(y for _, y in ring)
    width, height = max_x - min_x, max_y - min_y
    if not 0 < width <= SCALE // 50 or not 0 < height <= SCALE // 50:
        fail('Footprint extent outside planner bounds')
    # Multiplying coordinates by GRID makes every subdivision exactly integral.
    sides = edges([((x - min_x) * GRID, (y - min_y) * GRID) for x, y in ring])
    rows = [
        ''.join('1' if interior_cell(x * width, y * height, (x + 1) * width, (y + 1) * height, sides)
                else '0' for x in range(GRID))
        for y in range(GRID)
    ]
    return [min_x, min_y, max_x, max_y], rows


def partition(rows):
    width, height = len(rows[0]), len(rows)
    cumulative = [[0] * (width + 1) for _ in range(height + 1)]
    for y, row in enumerate(rows, 1):
        for x, cell in enumerate(row, 1):
            cumulative[y][x] = (cumulative[y - 1][x] + cumulative[y][x - 1]
                                - cumulative[y - 1][x - 1] + (cell == '1'))
    cache = {}

    def solve(x0, y0, x1, y1):
        key = (x0, y0, x1, y1)
        if key in cache:
            return cache[key]
        filled = cumulative[y1][x1] - cumulative[y0][x1] - cumulative[y1][x0] + cumulative[y0][x0]
        if filled == 0:
            best = (0, 0, ())
        elif filled == (x1 - x0) * (y1 - y0):
            best = (1, 2 * (x1 - x0 + y1 - y0), ((y0, x0, y1, x1),))
        else:
            alternatives = [(solve(x0, y0, x, y1), solve(x, y0, x1, y1)) for x in range(x0 + 1, x1)]
            alternatives.extend((solve(x0, y0, x1, y), solve(x0, y, x1, y1)) for y in range(y0 + 1, y1))
            best = min((a[0] + b[0], a[1] + b[1], tuple(sorted(a[2] + b[2]))) for a, b in alternatives)
        cache[key] = best
        return best

    count, perimeter, layout = solve(0, 0, width, height)
    tiles = [{'row': y0, 'column': x0, 'height': y1 - y0, 'width': x1 - x0}
             for y0, x0, y1, x1 in layout]
    return count, perimeter, tiles


def normalize(response, building):
    if not isinstance(response, list) or len(response) != 1 or not isinstance(response[0], dict):
        fail('No unique building footprint')
    row = response[0]
    if str(row.get('bin')) != str(building):
        fail('Footprint identifier mismatch')
    geometry = row.get('the_geom')
    if not isinstance(geometry, dict) or geometry.get('type') != 'MultiPolygon':
        fail('Unsupported footprint geometry')
    polys = geometry.get('coordinates')
    if (not isinstance(polys, list) or len(polys) != 1 or not isinstance(polys[0], list)
            or len(polys[0]) != 1 or not isinstance(polys[0][0], list)):
        fail('A single footprint ring is required')
    points = polys[0][0]
    if not 4 <= len(points) <= 65 or any(not isinstance(pt, list) or len(pt) != 2 for pt in points):
        fail('Invalid footprint ring size')
    ring = [(coordinate(pt[0], 180), coordinate(pt[1], 90)) for pt in points]
    if ring[0] != ring[-1]:
        fail('Footprint is not closed')
    ring = ring[:-1]
    validate_ring(ring)
    # Rotate to the least point and choose the lexicographically smaller direction.
    start = ring.index(min(ring))
    ring = ring[start:] + ring[:start]
    ring = min(ring, ring[:1] + ring[:0:-1])
    return ring


def observe(building):
    def sample():
        try:
            reply = gl.nondet.web.get(API.format(building))
            if reply.status != 200 or len(reply.body) > 16384:
                fail('Footprint source unavailable')
            data = json.loads(reply.body.decode('utf-8'), parse_float=str, object_pairs_hook=unique_keys)
        except (ValueError, UnicodeError):
            fail('Invalid footprint JSON')
        ring = normalize(data, building)
        bounds, rows = raster(ring)
        count, perimeter, tiles = partition(rows)
        polygon = [list(point) for point in ring]
        return {'bin': building, 'scale': SCALE, 'grid': GRID, 'bounds': bounds, 'ring': polygon,
                'geometry_sha256': sha256(encode(polygon).encode()).hexdigest(), 'interior': rows,
                'cell_count': sum(row.count('1') for row in rows), 'tile_count': count,
                'tile_perimeter': perimeter, 'tiles': tiles}

    def verify(leader):
        try:
            local = sample()
        except gl.vm.UserError as error:
            return not isinstance(leader, gl.vm.Return) and getattr(leader, 'message', None) == error.message
        except Exception:
            return False
        return isinstance(leader, gl.vm.Return) and local == leader.calldata

    return gl.vm.run_nondet_unsafe(sample, verify)


def valid_bin(building):
    if type(building) is not int or not 1_000_001 <= building <= 5_999_999 or building % 1_000_000 == 0:
        fail('Invalid building identifier')


class RoofQuilt(gl.Contract):
    plans: TreeMap[u256, str]
    count: u256

    def __init__(self):
        self.count = u256(0)

    @gl.public.write
    def plan(self, building: int) -> None:
        valid_bin(building)
        key = u256(building)
        if key in self.plans:
            fail('Footprint already planned')
        self.plans[key] = encode(observe(building))
        self.count = u256(int(self.count) + 1)

    @gl.public.view
    def get_plan(self, building: int) -> dict:
        valid_bin(building)
        key = u256(building)
        return json.loads(self.plans[key]) if key in self.plans else {}

    @gl.public.view
    def get_count(self) -> dict:
        return {'plans': int(self.count)}
