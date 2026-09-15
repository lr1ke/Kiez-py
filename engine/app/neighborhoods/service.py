import math
from typing import Protocol

from app.errors import AppError

FIELDS = "id,name,district,aliases,description,color,center,geometry,boundary_version"


async def catalog(db):
    return await db.rows(f"SELECT {FIELDS} FROM neighborhoods WHERE active ORDER BY display_order,id")


async def get_neighborhood(db, slug):
    n = await db.one(f"SELECT {FIELDS} FROM neighborhoods WHERE id=:id AND active", id=slug)
    if not n:
        raise AppError(404, "Neighborhood not found.")
    return n


class LocationResolver(Protocol):
    async def resolve(self, db, latitude: float, longitude: float, accuracy: float) -> dict: ...


def point_in_ring(lng, lat, ring):
    inside = False
    for (xi, yi), (xj, yj) in zip(ring, [ring[-1], *ring[:-1]]):
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
    return inside


def boundary_distance(lat, lng, rings):
    scale_x, scale_y = 111320 * math.cos(math.radians(lat)), 111320
    distance = math.inf
    for ring in rings:
        for a, b in zip(ring, ring[1:]):
            ax, ay = (a[0] - lng) * scale_x, (a[1] - lat) * scale_y
            bx, by = (b[0] - lng) * scale_x, (b[1] - lat) * scale_y
            dx, dy = bx - ax, by - ay
            denominator = dx * dx + dy * dy
            t = max(0, min(1, -(ax * dx + ay * dy) / denominator)) if denominator else 0
            distance = min(distance, math.hypot(ax + t * dx, ay + t * dy))
    return distance


class GeoJSONResolver:
    async def resolve(self, db, latitude, longitude, accuracy):
        for n in await catalog(db):
            geometry = n["geometry"]
            polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
            for rings in polygons:
                if point_in_ring(longitude, latitude, rings[0]) and not any(
                    point_in_ring(longitude, latitude, hole) for hole in rings[1:]
                ):
                    if accuracy > 250 or accuracy > boundary_distance(latitude, longitude, rings):
                        raise AppError(
                            422,
                            "Your location is too uncertain near a boundary. Move into the area and try again.",
                        )
                    return n
        raise AppError(
            422, "You are outside the supported neighborhood areas. You can still explore every Kiez."
        )
