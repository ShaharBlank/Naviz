import * as SQLite from "expo-sqlite";

import type { Coordinate, Locale, Place, SearchResponse } from "../../api/types";

const DATABASE_VERSION = "mobile-search-metro-2026-08-06";

const SEED: Place[] = [
  place("osm:place:habima", "Habima Square", "כיכר הבימה", 32.0733, 34.7799, "square"),
  place("osm:place:rabin", "Rabin Square", "כיכר רבין", 32.0808, 34.7806, "square"),
  place("osm:place:azrieli", "Azrieli Center", "מרכז עזריאלי", 32.0741, 34.7925, "landmark"),
  place(
    "osm:place:savidor",
    "Tel Aviv Savidor Center",
    "תל אביב סבידור מרכז",
    32.0832,
    34.7957,
    "station",
  ),
  place("osm:place:gordon", "Gordon Beach", "חוף גורדון", 32.0820, 34.7682, "beach"),
  place("osm:place:carmel", "Carmel Market", "שוק הכרמל", 32.0686, 34.7699, "market"),
];

let initialized: Promise<SQLite.SQLiteDatabase> | null = null;

export async function offlineSearchPlaces(
  query: string,
  locale: Locale,
  proximity?: Coordinate,
): Promise<SearchResponse> {
  const database = await databaseInstance();
  const token = `%${query.trim().toLocaleLowerCase()}%`;
  const rows = await database.getAllAsync<PlaceRow>(
    `SELECT id, name, name_he, latitude, longitude, category
       FROM places
      WHERE lower(name) LIKE ? OR name_he LIKE ?
      LIMIT 20`,
    token,
    token,
  );
  const results = rows.map(rowToPlace);
  if (proximity) {
    results.sort((left, right) => squaredDistance(left.coordinate, proximity) - squaredDistance(right.coordinate, proximity));
  } else if (locale === "he") {
    results.sort((left, right) => (left.name_he ?? left.name).localeCompare(right.name_he ?? right.name, "he"));
  }
  return { query, results: results.slice(0, 8), data_version: DATABASE_VERSION };
}

async function databaseInstance(): Promise<SQLite.SQLiteDatabase> {
  initialized ??= initialize();
  return initialized;
}

async function initialize(): Promise<SQLite.SQLiteDatabase> {
  const database = await SQLite.openDatabaseAsync("naviz-search.db");
  await database.execAsync(`
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS places (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      name_he TEXT,
      latitude REAL NOT NULL,
      longitude REAL NOT NULL,
      category TEXT NOT NULL
    );
  `);
  const version = await database.getFirstAsync<{ value: string }>(
    "SELECT value FROM metadata WHERE key = 'version'",
  );
  if (version?.value !== DATABASE_VERSION) {
    await database.withTransactionAsync(async () => {
      await database.runAsync("DELETE FROM places");
      for (const item of SEED) {
        await database.runAsync(
          `INSERT INTO places(id, name, name_he, latitude, longitude, category)
           VALUES (?, ?, ?, ?, ?, ?)`,
          item.id,
          item.name,
          item.name_he ?? null,
          item.coordinate.latitude,
          item.coordinate.longitude,
          item.category,
        );
      }
      await database.runAsync(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES ('version', ?)",
        DATABASE_VERSION,
      );
    });
  }
  return database;
}

interface PlaceRow {
  id: string;
  name: string;
  name_he: string | null;
  latitude: number;
  longitude: number;
  category: string;
}

function rowToPlace(row: PlaceRow): Place {
  return {
    id: row.id,
    name: row.name,
    name_he: row.name_he,
    subtitle: "Tel Aviv-Yafo · Offline index",
    coordinate: { latitude: row.latitude, longitude: row.longitude },
    category: row.category,
    confidence: "high",
  };
}

function place(
  id: string,
  name: string,
  nameHe: string,
  latitude: number,
  longitude: number,
  category: string,
): Place {
  return {
    id,
    name,
    name_he: nameHe,
    subtitle: "Tel Aviv-Yafo",
    coordinate: { latitude, longitude },
    category,
    confidence: "high",
  };
}

function squaredDistance(left: Coordinate, right: Coordinate): number {
  return (left.latitude - right.latitude) ** 2 + (left.longitude - right.longitude) ** 2;
}
