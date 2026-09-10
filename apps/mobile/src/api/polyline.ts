import type { Coordinate } from "./types";

export function decodePolyline(value: string, precision = 6): Coordinate[] {
  const factor = 10 ** precision;
  const coordinates: Coordinate[] = [];
  let index = 0;
  let latitude = 0;
  let longitude = 0;

  while (index < value.length) {
    const deltas: number[] = [];
    for (let coordinate = 0; coordinate < 2; coordinate += 1) {
      let result = 0;
      let shift = 0;
      let byte: number;
      do {
        byte = value.charCodeAt(index) - 63;
        index += 1;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20);
      deltas.push(result & 1 ? ~(result >> 1) : result >> 1);
    }
    latitude += deltas[0] ?? 0;
    longitude += deltas[1] ?? 0;
    coordinates.push({ latitude: latitude / factor, longitude: longitude / factor });
  }
  return coordinates;
}

export function encodePolyline(
  coordinates: Coordinate[],
  precision = 6,
): string {
  const factor = 10 ** precision;
  let previousLatitude = 0;
  let previousLongitude = 0;
  let result = "";

  for (const coordinate of coordinates) {
    const latitude = Math.round(coordinate.latitude * factor);
    const longitude = Math.round(coordinate.longitude * factor);
    result += encodeDelta(latitude - previousLatitude);
    result += encodeDelta(longitude - previousLongitude);
    previousLatitude = latitude;
    previousLongitude = longitude;
  }
  return result;
}

/**
 * Keep 3D shadow requests local to what a pedestrian can inspect around their
 * current position. Sending an entire inter-city route would calculate and
 * transfer invisible building polygons tens of kilometres away.
 */
export function shadowWindowPolyline(
  encodedPolyline: string,
  center: Coordinate,
  radiusM = 2_000,
): string {
  const coordinates = decodePolyline(encodedPolyline);
  if (coordinates.length < 3) return encodedPolyline;

  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;
  coordinates.forEach((coordinate, index) => {
    const distance = distanceMeters(coordinate, center);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  });

  let start = nearestIndex;
  let backwardDistance = 0;
  while (start > 0 && backwardDistance < radiusM) {
    backwardDistance += distanceMeters(coordinates[start]!, coordinates[start - 1]!);
    start -= 1;
  }

  let end = nearestIndex;
  let forwardDistance = 0;
  while (end < coordinates.length - 1 && forwardDistance < radiusM) {
    forwardDistance += distanceMeters(coordinates[end]!, coordinates[end + 1]!);
    end += 1;
  }

  if (start === 0 && end === coordinates.length - 1) return encodedPolyline;
  if (start === end) {
    end = Math.min(coordinates.length - 1, end + 1);
    start = Math.max(0, start - Number(end === nearestIndex));
  }
  return encodePolyline(coordinates.slice(start, end + 1));
}

function encodeDelta(delta: number): string {
  let value = delta < 0 ? ~(delta << 1) : delta << 1;
  let result = "";
  while (value >= 0x20) {
    result += String.fromCharCode((0x20 | (value & 0x1f)) + 63);
    value >>= 5;
  }
  return result + String.fromCharCode(value + 63);
}

export function distanceMeters(first: Coordinate, second: Coordinate): number {
  const earthRadiusM = 6_371_008.8;
  const toRadians = Math.PI / 180;
  const deltaLatitude = (second.latitude - first.latitude) * toRadians;
  const deltaLongitude = (second.longitude - first.longitude) * toRadians;
  const firstLatitude = first.latitude * toRadians;
  const secondLatitude = second.latitude * toRadians;
  const haversine =
    Math.sin(deltaLatitude / 2) ** 2 +
    Math.cos(firstLatitude) *
      Math.cos(secondLatitude) *
      Math.sin(deltaLongitude / 2) ** 2;
  return 2 * earthRadiusM * Math.asin(Math.min(1, Math.sqrt(haversine)));
}
