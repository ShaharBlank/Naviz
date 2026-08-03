import type { Coordinate } from "../../api/types";

export interface LocationSample {
  coordinate: Coordinate;
  accuracyM: number;
  headingDegrees: number | null;
}

export interface ProgressMatch {
  geometryIndex: number;
  distanceM: number;
  offRoute: boolean;
  arrived: boolean;
}

export class ProgressTracker {
  private lastIndex = 0;
  private offRouteStreak = 0;

  constructor(private readonly route: Coordinate[]) {
    if (route.length < 2) throw new Error("Route progress needs at least two points");
  }

  update(sample: LocationSample): ProgressMatch {
    const lower = Math.max(0, this.lastIndex - 2);
    const upper = Math.min(this.route.length, this.lastIndex + 30);
    let bestIndex = this.lastIndex;
    let bestScore = Number.POSITIVE_INFINITY;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (let index = lower; index < upper; index += 1) {
      const candidate = this.route[index];
      if (!candidate) continue;
      const distance = haversineM(sample.coordinate, candidate);
      let score = distance;
      const next = this.route[index + 1];
      if (sample.headingDegrees !== null && next) {
        const routeHeading = bearingDegrees(candidate, next);
        const delta = Math.abs(((sample.headingDegrees - routeHeading + 540) % 360) - 180);
        score += delta * 0.35;
      }
      if (index < this.lastIndex) score += (this.lastIndex - index) * 20;
      if (score < bestScore) {
        bestIndex = index;
        bestScore = score;
        bestDistance = distance;
      }
    }

    const threshold = Math.max(30, sample.accuracyM * 1.8);
    if (bestDistance > threshold) this.offRouteStreak += 1;
    else {
      this.offRouteStreak = 0;
      this.lastIndex = Math.max(this.lastIndex, bestIndex);
    }
    return {
      geometryIndex: bestIndex,
      distanceM: bestDistance,
      offRoute: this.offRouteStreak >= 3,
      arrived:
        bestIndex >= this.route.length - 2 &&
        haversineM(sample.coordinate, this.route[this.route.length - 1]!) < Math.max(20, threshold),
    };
  }
}

export function haversineM(first: Coordinate, second: Coordinate): number {
  const radius = 6_371_008.8;
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const lat1 = toRadians(first.latitude);
  const lat2 = toRadians(second.latitude);
  const deltaLat = lat2 - lat1;
  const deltaLon = toRadians(second.longitude - first.longitude);
  const value =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;
  return 2 * radius * Math.asin(Math.min(1, Math.sqrt(value)));
}

function bearingDegrees(first: Coordinate, second: Coordinate): number {
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const lat1 = toRadians(first.latitude);
  const lat2 = toRadians(second.latitude);
  const deltaLon = toRadians(second.longitude - first.longitude);
  const y = Math.sin(deltaLon) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

