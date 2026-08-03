import * as SecureStore from "expo-secure-store";

import type { RouteAlternative } from "../../api/types";

const KEY = "naviz-active-route-v1";

export async function cacheRoute(route: RouteAlternative): Promise<void> {
  await SecureStore.setItemAsync(KEY, JSON.stringify(route));
}

export async function loadCachedRoute(): Promise<RouteAlternative | null> {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return null;
  try {
    const route = JSON.parse(raw) as RouteAlternative;
    return new Date(route.expires_at).getTime() > Date.now() ? route : null;
  } catch {
    await SecureStore.deleteItemAsync(KEY);
    return null;
  }
}

export async function clearCachedRoute(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY);
}

