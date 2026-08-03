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

