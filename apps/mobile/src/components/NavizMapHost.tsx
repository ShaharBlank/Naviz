import Constants from "expo-constants";
import type { ComponentType } from "react";

import { ExpoGoNavizMap } from "./ExpoGoNavizMap";
import type { NavizMapProps } from "./NavizMap";

export type { MapDisplayMode } from "./NavizMap";

export function isExpoGoRuntime(appOwnership: string | null | undefined): boolean {
  return appOwnership === "expo";
}

export const NavizMap: ComponentType<NavizMapProps> = isExpoGoRuntime(
  Constants.appOwnership,
)
  ? ExpoGoNavizMap
  : // Deliberately deferred: Expo Go does not contain MapLibre's native module.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    (require("./NavizMap") as typeof import("./NavizMap")).NavizMap;
