import * as SQLite from "expo-sqlite";

import type { Coordinate, Locale, Place, SearchResponse } from "../../api/types";

const DATABASE_VERSION = "mobile-search-israel-2026-09-09";

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
  place("osm:place:western-wall", "Western Wall", "הכותל המערבי", 31.7767, 35.2345, "landmark"),
  place("osm:place:jerusalem-central", "Jerusalem Central Station", "התחנה המרכזית ירושלים", 31.7890, 35.2037, "station"),
  place("osm:place:haifa-center", "Haifa Center HaShmona", "חיפה מרכז השמונה", 32.8224, 34.9970, "station"),
  place("osm:place:beer-sheva-central", "Be'er Sheva Central Station", "התחנה המרכזית באר שבע", 31.2430, 34.7980, "station"),
  place("osm:place:eilat-central", "Eilat Central Station", "התחנה המרכזית אילת", 29.5560, 34.9510, "station"),
  place("osm:place:nazareth", "Nazareth", "נצרת", 32.6996, 35.3035, "city"),
  place("osm:place:tiberias", "Tiberias", "טבריה", 32.7940, 35.5310, "city"),
  place("osm:place:netanya", "Netanya", "נתניה", 32.3215, 34.8532, "city"),
  place("osm:place:ashdod", "Ashdod", "אשדוד", 31.8014, 34.6435, "city"),
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
    subtitle: "Israel · Offline index",
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
    subtitle: "Israel",
    coordinate: { latitude, longitude },
    category,
    confidence: "high",
  };
}

function squaredDistance(left: Coordinate, right: Coordinate): number {
  return (left.latitude - right.latitude) ** 2 + (left.longitude - right.longitude) ** 2;
}
