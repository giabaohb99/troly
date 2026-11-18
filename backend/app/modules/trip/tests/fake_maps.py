"""Google Maps Platform giả trong bộ nhớ (httpx.MockTransport). Tọa độ suy từ tên vùng trong chuỗi tìm,
thời gian chạy theo khoảng cách chim bay nhân 1,3 với 35 km/giờ (xe máy) hoặc 45 km/giờ (ô tô)."""

import hashlib
import json
import math
from urllib.parse import parse_qs

import httpx

AREAS = [
    ("rach mieu", (10.330, 106.370)),
    ("my thuan", (10.274, 105.910)),
    ("cat lai", (10.763, 106.795)),
    ("binh khanh", (10.640, 106.770)),
    ("tac suat", (10.411, 106.955)),
    ("dao khi", (10.420, 106.880)),
    ("lam vien", (10.420, 106.880)),
    ("phuoc thoi", (10.410, 107.230)),
    ("an nhut", (10.440, 107.150)),
    ("vung tau", (10.346, 107.084)),
    ("long hai", (10.390, 107.240)),
    ("nuoc ngot", (10.395, 107.255)),
    ("ky van", (10.400, 107.250)),
    ("minh dam", (10.440, 107.320)),
    ("so bong", (10.450, 107.310)),
    ("phuoc hai", (10.410, 107.270)),
    ("go cong", (10.360, 106.670)),
    ("tra vinh", (9.935, 106.345)),
    ("tra cuon", (9.900, 106.300)),
    ("can tho", (10.045, 105.747)),
]


def fold(text: str) -> str:
    from app.modules.trip.normalize import fold as real_fold

    return real_fold(text)


def area_of(query: str) -> tuple[float, float]:
    key = fold(query)
    for name, point in AREAS:
        if name in key:
            return point
    return (10.4, 107.0)


def jitter(query: str) -> tuple[float, float]:
    digest = hashlib.sha256(query.encode()).digest()
    return ((digest[0] - 128) / 128 * 0.01, (digest[1] - 128) / 128 * 0.01)


def km(a, b) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


class FakeMaps:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.places: dict[str, dict] = {}
        self.closed_mondays = {"bao tang"}
        self.unknown_queries: set[str] = set()
        self.ambiguous_queries: set[str] = set()
        self.fail_two_wheeler = False

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def calls(self, path_part: str) -> list[httpx.Request]:
        return [r for r in self.requests if path_part in r.url.host + r.url.path]

    def masks(self, path_part: str) -> list[str]:
        return [r.headers.get("x-goog-fieldmask", "") for r in self.calls(path_part)]

    def _place(self, query: str, n: int = 0) -> dict:
        pid = "pl_" + hashlib.sha1(f"{fold(query)}#{n}".encode()).hexdigest()[:12]
        if pid not in self.places:
            base = area_of(query)
            dj = jitter(query + str(n))
            lowered = fold(query)
            types = (
                ["museum"]
                if "bao tang" in lowered
                else ["restaurant"]
                if any(w in lowered for w in ("banh", "bun", "hu tieu", "com ", "hau", "oc ", "cafe", "chao"))
                else ["tourist_attraction"]
            )
            self.places[pid] = {
                "id": pid,
                "location": {"latitude": base[0] + dj[0], "longitude": base[1] + dj[1]},
                "formattedAddress": f"{query}, Việt Nam",
                "displayName": {"text": query},
                "types": types,
                "_query": lowered,
            }
        return self.places[pid]

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not request.headers.get("x-goog-api-key") and "key" not in request.url.params:
            return httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}})
        host, path = request.url.host, request.url.path
        if host == "places.googleapis.com" and path.endswith(":searchText"):
            body = json.loads(request.content)
            q = body["textQuery"]
            if fold(q) in self.unknown_queries:
                return httpx.Response(200, json={})
            count = 3 if fold(q) in self.ambiguous_queries else min(body.get("pageSize", 3), 3)
            ids = [self._place(q, i)["id"] for i in range(count)]
            if fold(q) in self.ambiguous_queries:
                for pid in ids:
                    self.places[pid]["formattedAddress"] = "Nơi khác, Việt Nam"
                    self.places[pid]["types"] = ["store"]
                    self.places[pid]["location"]["latitude"] += 3  # quá xa điểm trước
            return httpx.Response(200, json={"places": [{"id": i} for i in ids]})
        if host == "places.googleapis.com" and path.startswith("/v1/places/"):
            pid = path.rsplit("/", 1)[-1]
            place = self.places.get(pid)
            if place is None:
                return httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})
            mask = request.headers.get("x-goog-fieldmask", "")
            out = {"id": pid}
            for name in ("location", "formattedAddress", "types", "displayName"):
                if name in mask:
                    out[name] = place[name]
            if "OpeningHours" in mask:
                closed_monday = any(w in place["_query"] for w in self.closed_mondays)
                days = [d for d in range(7) if not (closed_monday and d == 1)]
                periods = [
                    {"open": {"day": d, "hour": 7, "minute": 0}, "close": {"day": d, "hour": 21, "minute": 0}}
                    for d in days
                ]
                out["regularOpeningHours"] = {"periods": periods}
                out["utcOffsetMinutes"] = 420
                out["businessStatus"] = "OPERATIONAL"
            return httpx.Response(200, json=out)
        if host == "routes.googleapis.com" and path.endswith(":computeRoutes"):
            body = json.loads(request.content)
            if body["travelMode"] == "TWO_WHEELER" and self.fail_two_wheeler:
                return httpx.Response(400, json={"error": {"status": "INVALID_ARGUMENT"}})
            pts = [body["origin"], *body.get("intermediates", []), body["destination"]]
            coords = [
                (p["location"]["latLng"]["latitude"], p["location"]["latLng"]["longitude"]) for p in pts
            ]
            speed = 35 if body["travelMode"] == "TWO_WHEELER" else 45
            legs = []
            for a, b in zip(coords, coords[1:], strict=False):
                d = km(a, b) * 1.3
                road = "Đi theo QL1A" if a[1] < 106.5 and b[1] < 106.9 else "Đi theo đường tỉnh"
                legs.append(
                    {
                        "distanceMeters": int(d * 1000),
                        "duration": f"{int(d / speed * 3600)}s",
                        "steps": [{"navigationInstruction": {"instructions": road}}],
                    }
                )
            return httpx.Response(200, json={"routes": [{"legs": legs, "warnings": []}]})
        if host == "routes.googleapis.com" and path.endswith(":computeRouteMatrix"):
            body = json.loads(request.content)
            origins = [
                (
                    o["waypoint"]["location"]["latLng"]["latitude"],
                    o["waypoint"]["location"]["latLng"]["longitude"],
                )
                for o in body["origins"]
            ]
            dests = [
                (
                    o["waypoint"]["location"]["latLng"]["latitude"],
                    o["waypoint"]["location"]["latLng"]["longitude"],
                )
                for o in body["destinations"]
            ]
            items = [
                {
                    "originIndex": i,
                    "destinationIndex": j,
                    "duration": f"{int(km(a, b) * 1.3 / 45 * 3600)}s",
                    "condition": "ROUTE_EXISTS",
                }
                for i, a in enumerate(origins)
                for j, b in enumerate(dests)
            ]
            return httpx.Response(200, json=items)
        if host == "maps.googleapis.com" and path.endswith("/geocode/json"):
            address = parse_qs(request.url.query.decode())["address"][0]
            place = self._place(address)
            loc = place["location"]
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "place_id": place["id"],
                            "formatted_address": place["formattedAddress"],
                            "geometry": {"location": {"lat": loc["latitude"], "lng": loc["longitude"]}},
                        }
                    ]
                },
            )
        if host == "mapstools.googleapis.com":
            body = json.loads(request.content)
            results = [
                {"url": u, "placeId": self._place("Hotel Quốc Hương Phước Hải")["id"]} for u in body["urls"]
            ]
            return httpx.Response(200, json={"results": results})
        return httpx.Response(404, json={})
