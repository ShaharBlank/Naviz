import * as Location from "expo-location";
import * as SecureStore from "expo-secure-store";
import * as TaskManager from "expo-task-manager";

const TASK_NAME = "naviz-active-navigation-location";
const LAST_FIX_KEY = "naviz-last-background-fix";

TaskManager.defineTask(TASK_NAME, async ({ data, error }) => {
  if (error || !data) return;
  const locations = (data as { locations: Location.LocationObject[] }).locations;
  const latest = locations.at(-1);
  if (latest) await SecureStore.setItemAsync(LAST_FIX_KEY, JSON.stringify(latest));
});

export async function requestNavigationPermission(): Promise<boolean> {
  const foreground = await Location.requestForegroundPermissionsAsync();
  if (foreground.status !== "granted") return false;
  const background = await Location.requestBackgroundPermissionsAsync();
  return background.status === "granted" || foreground.status === "granted";
}

export async function startBackgroundNavigation(): Promise<boolean> {
  const permission = await Location.getBackgroundPermissionsAsync();
  if (permission.status !== "granted") return false;
  const started = await Location.hasStartedLocationUpdatesAsync(TASK_NAME);
  if (started) return true;
  await Location.startLocationUpdatesAsync(TASK_NAME, {
    accuracy: Location.Accuracy.BestForNavigation,
    distanceInterval: 8,
    timeInterval: 4_000,
    pausesUpdatesAutomatically: false,
    showsBackgroundLocationIndicator: true,
    foregroundService: {
      notificationTitle: "Naviz navigation",
      notificationBody: "Turn-by-turn guidance is active",
      notificationColor: "#5B4BDB",
    },
  });
  return true;
}

export async function stopBackgroundNavigation(): Promise<void> {
  if (await Location.hasStartedLocationUpdatesAsync(TASK_NAME)) {
    await Location.stopLocationUpdatesAsync(TASK_NAME);
  }
  await SecureStore.deleteItemAsync(LAST_FIX_KEY);
}
