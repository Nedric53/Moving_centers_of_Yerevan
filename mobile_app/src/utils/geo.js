const EARTH_RADIUS = 6378137;

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function snapToGrid(value, grid) {
  const safe = clamp(value, grid.min, grid.max);
  const steps = Math.round((safe - grid.min) / grid.step);
  const snapped = grid.min + steps * grid.step;
  return Number(snapped.toFixed(2));
}

export function buildScenarioKey(transport, amenity) {
  return `${transport.toFixed(2)}_${amenity.toFixed(2)}`;
}

export function lonLatToRelativeMeters(lon, lat, origin) {
  const latRad = (origin.lat * Math.PI) / 180;
  const lonDelta = ((lon - origin.lon) * Math.PI) / 180;
  const latDelta = ((lat - origin.lat) * Math.PI) / 180;
  const x = lonDelta * EARTH_RADIUS * Math.cos(latRad);
  const y = latDelta * EARTH_RADIUS;
  return [x, y];
}

export function geoJsonToMapPolygons(geometry) {
  if (!geometry) return [];

  if (geometry.type === "Polygon") {
    return [polygonWithHolesToMapPolygon(geometry.coordinates)];
  }

  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.map((polygon) => polygonWithHolesToMapPolygon(polygon));
  }

  return [];
}

function polygonWithHolesToMapPolygon(coordinates) {
  return {
    coordinates: ringToMapCoordinates(coordinates[0] || []),
    holes: (coordinates.slice(1) || []).map((ring) => ringToMapCoordinates(ring))
  };
}

function ringToMapCoordinates(ring) {
  return ring.map((point) => ({
    longitude: point[0],
    latitude: point[1]
  }));
}

export function computeRegionFromGeometry(geometry, padding = 1.15) {
  const points = flattenLngLatPoints(geometry);
  if (!points.length) {
    return {
      latitude: 40.1775,
      longitude: 44.5126,
      latitudeDelta: 0.18,
      longitudeDelta: 0.18
    };
  }

  let minLon = Infinity;
  let maxLon = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;

  points.forEach(([lon, lat]) => {
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
  });

  const latitude = (minLat + maxLat) / 2;
  const longitude = (minLon + maxLon) / 2;
  const latitudeDelta = Math.max(0.04, (maxLat - minLat) * padding);
  const longitudeDelta = Math.max(0.04, (maxLon - minLon) * padding);

  return { latitude, longitude, latitudeDelta, longitudeDelta };
}

function flattenLngLatPoints(geometry) {
  if (!geometry) return [];

  if (geometry.type === "Polygon") {
    return geometry.coordinates.flat();
  }

  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.flat(2);
  }

  return [];
}

export function projectMetersToPath(geometry, width, height, range) {
  if (!geometry || !width || !height || !range) return "";

  const project = (x, y) => {
    const scale = Math.min(width, height) / (2 * range);
    return {
      x: width / 2 + x * scale,
      y: height / 2 - y * scale
    };
  };

  let path = "";

  const pushRing = (ring) => {
    if (!ring || ring.length < 3) return;
    ring.forEach((point, index) => {
      const projected = project(point[0], point[1]);
      path += `${index === 0 ? "M" : "L"} ${projected.x.toFixed(2)} ${projected.y.toFixed(2)} `;
    });
    path += "Z ";
  };

  if (geometry.type === "Polygon") {
    geometry.coordinates.forEach(pushRing);
  } else if (geometry.type === "MultiPolygon") {
    geometry.coordinates.forEach((polygon) => polygon.forEach(pushRing));
  }

  return path.trim();
}

export function convertYerevanGeomToMeters(geometry, origin) {
  if (!geometry) return null;

  if (geometry.type === "Polygon") {
    return {
      type: "Polygon",
      coordinates: geometry.coordinates.map((ring) =>
        ring.map((point) => lonLatToRelativeMeters(point[0], point[1], origin))
      )
    };
  }

  if (geometry.type === "MultiPolygon") {
    return {
      type: "MultiPolygon",
      coordinates: geometry.coordinates.map((polygon) =>
        polygon.map((ring) => ring.map((point) => lonLatToRelativeMeters(point[0], point[1], origin)))
      )
    };
  }

  return null;
}
