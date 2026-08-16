import type { Coordinate } from "../../api/types";

export interface LocationSample {
  coordinate: Coordinate;
  accuracyM: number;
  headingDegrees: number | null;
}

export interface ProgressMatch {
  geometryIndex: number;
  distanceM: number;
  remainingDistanceM: number;
  progressFraction: number;
  offRoute: boolean;
  arrived: boolean;
}

interface SegmentMatch {
  segmentIndex: number;
  fraction: number;
  distanceM: number;
  headingDegrees: number;
}

/**
 * Route-aware matcher over line segments. It uses accuracy-adjusted emissions,
 * heading, forward progress, and three-fix hysteresis instead of snapping to a
 * sampled vertex.
 */
export class ProgressTracker {
  private lastSegment = 0;
  private lastProgressM = 0;
  private offRouteStreak = 0;
  private readonly cumulativeM: number[];
  private readonly totalDistanceM: number;

  constructor(private readonly route: Coordinate[]) {
    if (route.length < 2) throw new Error("Route progress needs at least two points");
    this.cumulativeM = [0];
    for (let index = 0; index < route.length - 1; index += 1) {
      this.cumulativeM.push(
        this.cumulativeM[index]! + haversineM(route[index]!, route[index + 1]!),
      );
    }
    this.totalDistanceM = this.cumulativeM.at(-1) ?? 0;
  }

  update(sample: LocationSample): ProgressMatch {
    const lower = Math.max(0, this.lastSegment - 8);
    const upper = Math.min(this.route.length - 1, this.lastSegment + 120);
    let best: SegmentMatch | null = null;
    let bestScore = Number.POSITIVE_INFINITY;

    for (let index = lower; index < upper; index += 1) {
      const first = this.route[index];
      const second = this.route[index + 1];
      if (!first || !second) continue;
      const match = projectToSegment(sample.coordinate, first, second, index);
      const segmentLength = haversineM(first, second);
      const progressM = this.cumulativeM[index]! + match.fraction * segmentLength;
      let score = match.distanceM;
      if (sample.headingDegrees !== null) {
        const delta = angleDifference(sample.headingDegrees, match.headingDegrees);
        score += Math.min(45, delta) * 0.35;
      }
      if (progressM + Math.max(25, sample.accuracyM) < this.lastProgressM) {
        score += Math.min(250, this.lastProgressM - progressM) * 0.8;
      }
      if (score < bestScore) {
        best = match;
        bestScore = score;
      }
    }

    const match = best ?? projectToSegment(
      sample.coordinate,
      this.route[this.lastSegment]!,
      this.route[this.lastSegment + 1]!,
      this.lastSegment,
    );
    const segmentLength = haversineM(
      this.route[match.segmentIndex]!,
      this.route[match.segmentIndex + 1]!,
    );
    const candidateProgress =
      this.cumulativeM[match.segmentIndex]! + match.fraction * segmentLength;
    const threshold = Math.max(28, sample.accuracyM * 1.8);
    const impossibleJump = candidateProgress > this.lastProgressM + 2_000;
    if (match.distanceM > threshold || impossibleJump) {
      this.offRouteStreak += 1;
    } else {
      this.offRouteStreak = 0;
      this.lastSegment = Math.max(this.lastSegment, match.segmentIndex);
      this.lastProgressM = Math.max(this.lastProgressM, candidateProgress);
    }
    const remainingDistanceM = Math.max(0, this.totalDistanceM - this.lastProgressM);
    const destinationDistance = haversineM(sample.coordinate, this.route.at(-1)!);
    const arrived =
      remainingDistanceM <= Math.max(35, threshold) &&
      destinationDistance <= Math.max(30, threshold);
    return {
      geometryIndex: Math.min(this.route.length - 1, match.segmentIndex + 1),
      distanceM: match.distanceM,
      remainingDistanceM,
      progressFraction: this.totalDistanceM > 0 ? this.lastProgressM / this.totalDistanceM : 0,
      offRoute: this.offRouteStreak >= 3,
      arrived,
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

function projectToSegment(
  point: Coordinate,
  first: Coordinate,
  second: Coordinate,
  segmentIndex: number,
): SegmentMatch {
  const latitudeScale = 111_320;
  const longitudeScale = latitudeScale * Math.cos((point.latitude * Math.PI) / 180);
  const bx = (second.longitude - first.longitude) * longitudeScale;
  const by = (second.latitude - first.latitude) * latitudeScale;
  const px = (point.longitude - first.longitude) * longitudeScale;
  const py = (point.latitude - first.latitude) * latitudeScale;
  const squaredLength = bx * bx + by * by;
  const fraction = squaredLength > 0 ? Math.max(0, Math.min(1, (px * bx + py * by) / squaredLength)) : 0;
  const dx = px - fraction * bx;
  const dy = py - fraction * by;
  return {
    segmentIndex,
    fraction,
    distanceM: Math.hypot(dx, dy),
    headingDegrees: bearingDegrees(first, second),
  };
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

function angleDifference(first: number, second: number): number {
  return Math.abs(((first - second + 540) % 360) - 180);
}
