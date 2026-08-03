import {
  Camera,
  GeoJSONSource,
  Layer,
  Map,
  UserLocation,
} from "@maplibre/maplibre-react-native";
import { memo, useMemo } from "react";
import { StyleSheet, View } from "react-native";

import { decodePolyline } from "../api/polyline";
import type { Coordinate, RouteAlternative } from "../api/types";
import { colors } from "../theme/tokens";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

interface Props {
  route: RouteAlternative | null;
  userCoordinate: Coordinate | null;
  following: boolean;
}

function NavizMapComponent({ route, userCoordinate, following }: Props) {
  const geometry = useMemo(
    () => (route ? decodePolyline(route.encoded_polyline) : []),
    [route],
  );
  const line = useMemo<GeoJSON.Feature<GeoJSON.LineString>>(
    () => ({
      type: "Feature" as const,
      properties: {},
      geometry: {
        type: "LineString" as const,
        coordinates: geometry.map(({ longitude, latitude }) => [longitude, latitude]),
      },
    }),
    [geometry],
  );
  const segments = useMemo<GeoJSON.FeatureCollection<GeoJSON.LineString>>(
    () => ({
      type: "FeatureCollection" as const,
      features:
        route?.annotations
          .map((annotation) => ({
            type: "Feature" as const,
            properties: { classification: annotation.classification },
            geometry: {
              type: "LineString" as const,
              coordinates: geometry
                .slice(annotation.start_index, annotation.end_index + 1)
                .map(({ longitude, latitude }) => [longitude, latitude]),
            },
          }))
          .filter((feature) => feature.geometry.coordinates.length >= 2) ?? [],
    }),
    [geometry, route?.annotations],
  );
  const crossings = useMemo<GeoJSON.FeatureCollection<GeoJSON.Point>>(
    () => ({
      type: "FeatureCollection" as const,
      features:
        route?.annotations.flatMap((annotation) => {
          const coordinate = geometry[annotation.start_index];
          if (!annotation.crossing_kind || !coordinate) return [];
          return [{
            type: "Feature" as const,
            properties: { crossing: annotation.crossing_kind },
            geometry: {
              type: "Point" as const,
              coordinates: [coordinate.longitude, coordinate.latitude],
            },
          }];
        }) ?? [],
    }),
    [geometry, route?.annotations],
  );

  return (
    <View style={styles.container} accessibilityLabel="Naviz map">
      <Map style={styles.map} mapStyle={MAP_STYLE}>
        {following ? (
          <Camera trackUserLocation="heading" zoom={17} />
        ) : route ? (
          <Camera
            bounds={route.bbox}
            padding={{ top: 130, right: 40, bottom: 340, left: 40 }}
            duration={600}
          />
        ) : (
          <Camera
            initialViewState={{
              center: userCoordinate
                ? [userCoordinate.longitude, userCoordinate.latitude]
                : [34.7799, 32.0733],
              zoom: 13.5,
            }}
          />
        )}
        <UserLocation animated accuracy heading />
        {route && geometry.length >= 2 ? (
          <>
            <GeoJSONSource id="route-border" data={line}>
              <Layer
                id="route-border-line"
                type="line"
                paint={{ "line-color": colors.surface, "line-width": 10, "line-opacity": 0.95 }}
                layout={{ "line-cap": "round" }}
              />
            </GeoJSONSource>
            <GeoJSONSource id="route" data={line}>
              <Layer
                id="route-line"
                type="line"
                paint={{ "line-color": colors.primary, "line-width": 7 }}
                layout={{ "line-cap": "round" }}
              />
            </GeoJSONSource>
            <GeoJSONSource id="route-segments" data={segments}>
              <Layer
                id="route-shade-lines"
                type="line"
                filter={["==", ["get", "classification"], "shade"]}
                paint={{ "line-color": colors.shade, "line-width": 7 }}
                layout={{ "line-cap": "round" }}
              />
              <Layer
                id="route-mixed-lines"
                type="line"
                filter={["==", ["get", "classification"], "mixed"]}
                paint={{ "line-color": colors.mixed, "line-width": 7, "line-dasharray": [2, 1] }}
                layout={{ "line-cap": "round" }}
              />
              <Layer
                id="route-sun-lines"
                type="line"
                filter={["==", ["get", "classification"], "sun"]}
                paint={{ "line-color": colors.sun, "line-width": 7, "line-dasharray": [0.5, 1.5] }}
                layout={{ "line-cap": "round" }}
              />
            </GeoJSONSource>
            <GeoJSONSource id="route-crossings" data={crossings}>
              <Layer
                id="route-crossing-points"
                type="circle"
                paint={{
                  "circle-color": colors.surface,
                  "circle-radius": 5,
                  "circle-stroke-color": colors.ink,
                  "circle-stroke-width": 2,
                }}
              />
            </GeoJSONSource>
          </>
        ) : null}
      </Map>
    </View>
  );
}

export const NavizMap = memo(NavizMapComponent);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#E5E7EB" },
  map: { flex: 1 },
});
