import { View } from "react-native";
import Svg, {
  Circle,
  Defs,
  Ellipse,
  G,
  LinearGradient,
  Path,
  Rect,
  Stop,
} from "react-native-svg";

import type { TravelMode } from "../api/types";
import { colors } from "../theme/tokens";

interface Props {
  mode: TravelMode;
  displayMode: "2d" | "3d";
  rotationDegrees?: number;
  active?: boolean;
  accessibilityLabel?: string;
}

export function NavigationAvatar({
  mode,
  displayMode,
  rotationDegrees = 0,
  active = true,
  accessibilityLabel,
}: Props) {
  const kind = navigationAvatarKind(mode);
  const color = navigationAvatarColor(mode);
  const threeDimensional = displayMode === "3d";
  return (
    <View
      accessible={Boolean(accessibilityLabel)}
      accessibilityRole={accessibilityLabel ? "image" : undefined}
      accessibilityLabel={accessibilityLabel}
      style={{
        width: 58,
        height: 66,
        opacity: active ? 1 : 0.82,
        transform: [
          { rotate: `${rotationDegrees}deg` },
          { scale: active ? 1 : 0.78 },
        ],
      }}
    >
      <Svg width={58} height={66} viewBox="0 0 58 66">
        <Defs>
          <LinearGradient id="body" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor="#FFFFFF" stopOpacity="0.95" />
            <Stop offset="0.18" stopColor={color} />
            <Stop offset="1" stopColor={color} stopOpacity="0.72" />
          </LinearGradient>
          <LinearGradient id="glass" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#E0F2FE" />
            <Stop offset="1" stopColor="#164E63" />
          </LinearGradient>
        </Defs>
        {threeDimensional ? (
          <Ellipse
            cx="29"
            cy="58"
            rx="18"
            ry="5"
            fill="#0F172A"
            opacity="0.22"
          />
        ) : null}
        {kind === "person" ? (
          <PersonGlyph color={color} threeDimensional={threeDimensional} />
        ) : kind === "two_wheeler" ? (
          <TwoWheelerGlyph color={color} threeDimensional={threeDimensional} />
        ) : (
          <VehicleGlyph
            kind={kind}
            color={color}
            threeDimensional={threeDimensional}
          />
        )}
      </Svg>
    </View>
  );
}

type AvatarKind = "person" | "two_wheeler" | "car" | "truck" | "transit";

export function navigationAvatarKind(mode: TravelMode): AvatarKind {
  if (mode === "walk") return "person";
  if (mode === "bike" || mode === "scooter" || mode === "motorcycle") {
    return "two_wheeler";
  }
  if (mode === "truck") return "truck";
  if (mode === "transit" || mode.endsWith("_transit")) return "transit";
  return "car";
}

export function navigationAvatarColor(mode: TravelMode): string {
  if (mode === "walk") return colors.shade;
  if (mode === "bike" || mode === "scooter") return "#059669";
  if (mode === "transit" || mode.endsWith("_transit")) return "#C026D3";
  if (mode === "motorcycle") return "#7C3AED";
  if (mode === "truck") return "#EA580C";
  return colors.primary;
}

function VehicleGlyph({
  kind,
  color,
  threeDimensional,
}: {
  kind: Exclude<AvatarKind, "person" | "two_wheeler">;
  color: string;
  threeDimensional: boolean;
}) {
  if (!threeDimensional) {
    const width = kind === "car" ? 26 : 30;
    const left = (58 - width) / 2;
    return (
      <G>
        <Path
          d={`M29 5 L${left + width - 4} 12 Q${left + width} 16 ${left + width} 23 V49 Q${left + width} 56 ${left + width - 7} 58 H${left + 7} Q${left} 56 ${left} 49 V23 Q${left} 16 ${left + 4} 12 Z`}
          fill="url(#body)"
          stroke="#FFFFFF"
          strokeWidth="2.2"
        />
        <Path
          d={`M${left + 5} 20 Q29 14 ${left + width - 5} 20 L${left + width - 7} 31 H${left + 7} Z`}
          fill="url(#glass)"
          opacity="0.96"
        />
        <Rect
          x={left + 5}
          y="40"
          width={width - 10}
          height="9"
          rx="4"
          fill="#FFFFFF"
          opacity="0.2"
        />
        <Path
          d="M24 7 L29 1 L34 7"
          fill={color}
          stroke="#FFFFFF"
          strokeWidth="1.5"
        />
        <Rect
          x={left + 3}
          y="51"
          width="6"
          height="3.5"
          rx="1.5"
          fill="#FDE68A"
        />
        <Rect
          x={left + width - 9}
          y="51"
          width="6"
          height="3.5"
          rx="1.5"
          fill="#FDE68A"
        />
      </G>
    );
  }
  const bodyWidth = kind === "car" ? 34 : 40;
  const left = (58 - bodyWidth) / 2;
  return (
    <G>
      <Rect x={left - 2} y="39" width="5" height="15" rx="2.5" fill="#111827" />
      <Rect
        x={left + bodyWidth - 3}
        y="39"
        width="5"
        height="15"
        rx="2.5"
        fill="#111827"
      />
      <Path
        d={`M${left + 6} 14 Q29 7 ${left + bodyWidth - 6} 14 L${left + bodyWidth} 43 Q${left + bodyWidth + 1} 54 ${left + bodyWidth - 8} 57 H${left + 8} Q${left - 1} 54 ${left} 43 Z`}
        fill="url(#body)"
        stroke="#FFFFFF"
        strokeWidth="2.4"
      />
      <Path
        d={`M${left + 8} 18 Q29 12 ${left + bodyWidth - 8} 18 L${left + bodyWidth - 6} 34 H${left + 6} Z`}
        fill="url(#glass)"
        stroke="#BAE6FD"
        strokeWidth="1"
      />
      <Path
        d={`M${left + 4} 39 Q29 45 ${left + bodyWidth - 4} 39`}
        fill="none"
        stroke="#FFFFFF"
        strokeOpacity="0.38"
        strokeWidth="2"
      />
      <Rect x={left + 4} y="47" width="8" height="4" rx="2" fill="#FB7185" />
      <Rect
        x={left + bodyWidth - 12}
        y="47"
        width="8"
        height="4"
        rx="2"
        fill="#FB7185"
      />
      <Rect x="25" y="52" width="8" height="2.5" rx="1.25" fill="#E2E8F0" />
    </G>
  );
}

function TwoWheelerGlyph({
  color,
  threeDimensional,
}: {
  color: string;
  threeDimensional: boolean;
}) {
  return threeDimensional ? (
    <G>
      <Ellipse
        cx="29"
        cy="53"
        rx="8"
        ry="4"
        fill="#111827"
        stroke="#FFFFFF"
        strokeWidth="1.7"
      />
      <Path
        d="M29 50 L29 32 L20 24 M29 32 L38 24"
        fill="none"
        stroke={color}
        strokeWidth="5"
        strokeLinecap="round"
      />
      <Path
        d="M20 24 Q29 19 38 24"
        fill="none"
        stroke="#0F172A"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <Path
        d="M24 31 Q29 23 34 31 L37 42 H21 Z"
        fill="url(#body)"
        stroke="#FFFFFF"
        strokeWidth="1.8"
      />
      <Circle
        cx="29"
        cy="19"
        r="6"
        fill="#F1C27D"
        stroke="#FFFFFF"
        strokeWidth="1.6"
      />
      <Path d="M23 18 Q29 10 35 18" fill={color} />
      <Path
        d="M29 15 L29 8"
        stroke={color}
        strokeWidth="3"
        strokeLinecap="round"
      />
    </G>
  ) : (
    <G>
      <Ellipse
        cx="29"
        cy="13"
        rx="6"
        ry="9"
        fill="#111827"
        stroke="#FFFFFF"
        strokeWidth="2"
      />
      <Path
        d="M29 19 V47"
        stroke={color}
        strokeWidth="6"
        strokeLinecap="round"
      />
      <Circle
        cx="29"
        cy="31"
        r="8"
        fill="url(#body)"
        stroke="#FFFFFF"
        strokeWidth="1.8"
      />
      <Ellipse
        cx="29"
        cy="53"
        rx="6"
        ry="9"
        fill="#111827"
        stroke="#FFFFFF"
        strokeWidth="2"
      />
      <Path
        d="M21 25 H37"
        stroke="#0F172A"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <Path
        d="M25 6 L29 1 L33 6"
        fill={color}
        stroke="#FFFFFF"
        strokeWidth="1.5"
      />
    </G>
  );
}

function PersonGlyph({
  color,
  threeDimensional,
}: {
  color: string;
  threeDimensional: boolean;
}) {
  return threeDimensional ? (
    <G>
      <Circle
        cx="29"
        cy="15"
        r="7"
        fill="#F1C27D"
        stroke="#FFFFFF"
        strokeWidth="1.8"
      />
      <Path d="M23 13 Q29 5 35 13 V16 H23 Z" fill={color} />
      <Path
        d="M23 24 Q29 20 35 24 L37 41 L30 43 L28 32 L26 43 L19 41 Z"
        fill="url(#body)"
        stroke="#FFFFFF"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <Path
        d="M23 27 L15 38 M35 27 L42 34"
        stroke={color}
        strokeWidth="5"
        strokeLinecap="round"
      />
      <Path
        d="M25 41 L20 56 M32 41 L39 54"
        stroke="#172554"
        strokeWidth="6"
        strokeLinecap="round"
      />
    </G>
  ) : (
    <G>
      <Ellipse
        cx="29"
        cy="33"
        rx="10"
        ry="16"
        fill="url(#body)"
        stroke="#FFFFFF"
        strokeWidth="1.8"
      />
      <Circle
        cx="29"
        cy="12"
        r="7.5"
        fill="#F1C27D"
        stroke="#FFFFFF"
        strokeWidth="1.8"
      />
      <Path d="M22 11 Q29 2 36 11 L35 14 H23 Z" fill={color} />
      <Path
        d="M21 26 L13 40 M37 26 L45 40"
        stroke={color}
        strokeWidth="5"
        strokeLinecap="round"
      />
      <Path
        d="M25 45 L21 59 M33 45 L37 59"
        stroke="#172554"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <Path
        d="M25 5 L29 0 L33 5"
        fill="#FFFFFF"
        stroke="#FFFFFF"
        strokeWidth="1.5"
      />
    </G>
  );
}
