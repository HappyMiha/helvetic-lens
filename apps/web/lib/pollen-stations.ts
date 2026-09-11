// Public directory metadata only. Never import the retained concentrations into UI.
export const pollenStationSource = {
  capturedAt: "2026-09-11T06:42:35.407424+00:00",
  sha256: "d367bf17c1262f5bd8c913147162b9f366d1bfcc88e0799c2c29282936bb827b",
  url: "https://data.geo.admin.ch/ch.meteoschweiz.ogd-pollen/ogd-pollen_meta_stations.csv",
  documentation:
    "https://opendatadocs.meteoswiss.ch/a-data-groundbased/a7-pollen-stations",
  terms: "https://opendatadocs.meteoswiss.ch/general/terms-of-use",
  attribution: "Source: MeteoSwiss",
} as const;
export type Station = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
};
export type Point = { latitude: number; longitude: number };
export const pollenStations: readonly Station[] = [
  { id: "PBE", name: "Bern", latitude: 46.950342, longitude: 7.424661 },
  { id: "PBS", name: "Basel", latitude: 47.5618, longitude: 7.583931 },
  { id: "PBU", name: "Buchs, SG", latitude: 47.173267, longitude: 9.472614 },
  {
    id: "PCF",
    name: "La Chaux-de-Fonds",
    latitude: 47.113514,
    longitude: 6.832,
  },
  {
    id: "PDS",
    name: "Davos / Wolfgang",
    latitude: 46.829092,
    longitude: 9.855489,
  },
  { id: "PGE", name: "Genève", latitude: 46.191969, longitude: 6.147544 },
  {
    id: "PLO",
    name: "Locarno / Monti",
    latitude: 46.172547,
    longitude: 8.787389,
  },
  { id: "PLS", name: "Lausanne", latitude: 46.524103, longitude: 6.644825 },
  { id: "PLU", name: "Lugano", latitude: 46.004231, longitude: 8.960631 },
  { id: "PLZ", name: "Luzern", latitude: 47.057678, longitude: 8.296803 },
  {
    id: "PMU",
    name: "Münsterlingen",
    latitude: 47.630206,
    longitude: 9.236878,
  },
  { id: "PNE", name: "Neuchâtel", latitude: 47.000269, longitude: 6.949828 },
  { id: "PPY", name: "Payerne", latitude: 46.813403, longitude: 6.942939 },
  { id: "PSN", name: "Sion", latitude: 46.235403, longitude: 7.384606 },
  { id: "PZH", name: "Zürich", latitude: 47.378225, longitude: 8.565644 },
];
export function validPoint(point: Point): boolean {
  return (
    Number.isFinite(point.latitude) &&
    Number.isFinite(point.longitude) &&
    Math.abs(point.latitude) <= 90 &&
    Math.abs(point.longitude) <= 180
  );
}
export function stationDistanceKm(from: Point, to: Point): number | null {
  if (!validPoint(from) || !validPoint(to)) return null;
  const radians = (angle: number) => (angle * Math.PI) / 180;
  const a =
    Math.sin(radians(to.latitude - from.latitude) / 2) ** 2 +
    Math.cos(radians(from.latitude)) *
      Math.cos(radians(to.latitude)) *
      Math.sin(radians(to.longitude - from.longitude) / 2) ** 2;
  return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, a))));
}
export function orderedPollenStations(point: Point | null, locale: string) {
  return pollenStations
    .map((station) => ({
      ...station,
      distance: point ? stationDistanceKm(point, station) : null,
    }))
    .sort(
      (a, b) =>
        (a.distance !== null && b.distance !== null
          ? a.distance - b.distance
          : 0) || a.name.localeCompare(b.name, locale),
    );
}
// Documented channel existence, not station-level or current live availability.
export function pollenChannels(allergen: string) {
  return {
    observation: [
      "alder",
      "birch",
      "hazel",
      "beech",
      "ash",
      "oak",
      "grasses",
    ].includes(allergen),
    forecast: ["alder", "birch", "hazel", "grasses", "ragweed"].includes(
      allergen,
    ),
  };
}
