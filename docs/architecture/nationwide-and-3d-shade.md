# Nationwide Israel and 3D shade architecture

Status: proposed implementation contract  
Last reviewed: 2026-09-09  
Scope: nationwide Naviz routing, policy comparison, side-aware shade routing, and
3D shade visualization. This document does not claim that these capabilities are
already deployed.

The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative. A release
may advertise a capability only after its corresponding gate in this document
passes.

## Decision summary

1. Nationwide coverage is built from immutable, checksummed national data
   bundles. No route request downloads OSM, rebuilds a graph, or changes the
   active dataset.
2. Valhalla is the nationwide street-routing engine. Naviz's compact
   Range-RAPTOR remains the low-memory transit implementation; OpenTripPlanner
   is the scale-up adapter. Both remain behind the existing normalized API.
3. A route is called optimal only relative to a named dataset snapshot, a
   deterministic cost model, a departure time, and declared hard constraints.
   Naviz MUST NOT imply live-traffic optimality without a validated live road
   traffic source.
4. Planning returns all materially different policies for the selected mode in
   one response. The user compares Fastest, Fewer Lights, Balanced Shade, and so
   on; the UI does not require a preference choice before calculation.
5. Shade quality is tiered per route segment. Nationwide routing is possible
   before nationwide high-confidence shade data is possible.
6. MapLibre Native renders buildings and the route, but it does not currently
   cast building shadows onto the ground. Naviz therefore computes time-specific
   ground-shadow polygons itself and renders them as a separate map layer.
7. A production-grade nationwide service cannot honestly run on Render Free.
   The free instance remains a single-user showcase/gateway while measured,
   memory-sized routing services are deployed separately.

## Product truth and capability tiers

Coverage and quality are properties of a coordinate and time, not of the brand
as a whole. `GET /v1/data/status` and every route response MUST expose the active
manifest digest, source timestamps, coverage polygon, engine profile, and the
lowest capability tier encountered by the route.

### Nationwide navigation tiers

| Tier | May be shown to users as | Required evidence | Explicit limitation |
| --- | --- | --- | --- |
| N0 | Unsupported area | No validated routable graph or source is stale past its release limit | Do not calculate a plausible-looking line |
| N1 | Nationwide scheduled navigation | Connected, validated OSM graph and current national GTFS snapshot | ETA uses modeled/base speeds; transit is scheduled |
| N2 | Data-qualified navigation | N1 plus sufficiently complete signals, restrictions, accessibility, or bicycle attributes for the requested policy | Confidence and missing tags remain visible in route details |
| N3 | Field-validated navigation | N2 plus the regional field corpus and release thresholds in this document | Validation applies only to the named region, modes, and dataset version |

`N1` is the first nationwide launch target. `N2` and `N3` are earned region by
region. "Fastest" at N1 means the minimum modeled cost on the active graph, not
the fastest route in unobserved live traffic.

### Shade tiers

| Tier | Inputs | Allowed behavior |
| --- | --- | --- |
| S0 unavailable | Building, sidewalk, or solar inputs are absent/invalid | Return Fastest only and `shade_unavailable`; do not fabricate a percentage |
| S1 estimated | Footprints plus estimated/default heights and/or inferred sidewalk offsets | Display an estimated exposure range. Balanced Shade may be experimental; Maximum Shade MUST NOT be called verified |
| S2 modeled | Explicit or validated sidewalks, legal crossings, attributed height/level data, and a validated horizon profile | Return Fastest, Balanced Shade, and Maximum Shade with confidence broken down by segment |
| S3 field-validated | S2 plus local canopy data and the field accuracy gate | Advertise high-confidence shade routing for that named coverage polygon and season |

If a route crosses tiers, calculations retain segment-level quality and the card
uses the minimum tier. A lower tier MUST not be hidden by averaging confidence.
When no fully shaded valid route exists, Naviz returns the least-exposed valid
route and states that outcome in the comparison card, not in a generic alarming
banner.

### 3D display tiers

| Tier | Behavior |
| --- | --- |
| V0 | 2D route and shade-pattern fallback |
| V1 | Extruded buildings with cosmetic sun-synchronized lighting; no ground-shadow claim |
| V2 | Time-specific ground-shadow polygons, exact for the published 2.5-D scene model |
| V3 | V2 plus locally validated height/canopy/terrain inputs and physical-device performance gate |

"Exact" in V2 means geometrically exact for the versioned 2.5-D prisms and solar
position. It does not mean that every balcony, tree, roof shape, construction
change, or terrain discontinuity exists in the source data.

## Nationwide data platform

### Source registry

Every source MUST have a registry entry containing owner, canonical URL,
retrieval method, expected cadence, source timestamp, checksum, coordinate
reference system, geographic scope, license/terms URL, required attribution,
redistribution decision, and a data steward. A source without a recorded
redistribution decision cannot enter a public artifact.

| Input | Use | Refresh target | Decision |
| --- | --- | --- | --- |
| [Geofabrik Israel and Palestine OSM PBF](https://download.geofabrik.de/asia/israel-and-palestine.html) | Streets, restrictions, sidewalks, crossings, signals, buildings, names, addresses | Acquire daily; release weekly or after a critical fix | Clip to an explicit Naviz coverage polygon. The extract name does not define product borders or labels |
| [Official Ministry of Transport GTFS](https://gtfs.mot.gov.il/gtfsfiles/) | Nationwide scheduled transit | Acquire and validate nightly | Pin the exact zip checksum and service date in every itinerary |
| [Official Israel SIRI ICD 2.8](https://www.gov.il/BlobFolder/generalpage/real_time_information_siri/he/ICD_SM_28_31.pdf) | Real-time transit predictions | Continuous only after authorized credentials | Implement an Israel SIRI-SM normalizer; do not pretend OTP's ET/SX adapters consume SIRI-SM |
| [National tree-canopy dataset](https://data.gov.il/dataset/nationalcanopytrees) | Canopy occlusion/confidence in built-up municipal areas | On source change | Its catalog says `Other (Open)` rather than a precise license. Redistribution is blocked until terms are recorded and approved |
| Licensed municipal building/tree/crossing data | Local quality upgrades | Per publisher cadence | Isolated adapters; provenance survives merges; no unrecorded scraping |
| [Overture Buildings](https://docs.overturemaps.org/guides/buildings/) | Gap-fill footprints and available height/floor attributes | Monthly candidate build | Use only with feature provenance/confidence and ODbL attribution; never assume complete height coverage |
| Approved DEM, after a separate ADR | Terrain correction for sloped areas | Source dependent | Until selected and validated, lower shade confidence on material slopes rather than inventing terrain |

The Geofabrik extract and national GTFS are acquisition inputs, not runtime
services. Public Nominatim MUST NOT be used for client autocomplete. Search is
served from Naviz's own bilingual SQLite FTS5 index built from the pinned bundle.

### Artifact set

One release manifest references independently replaceable artifacts:

```text
manifest.json
street/valhalla-tiles.tar
street/logical-signals.parquet
street/sidewalk-graph-<cell>.bin
transit/range-raptor.bin
transit/otp.graph.obj                 # scale profile only
search/israel-search.sqlite3
shade/buildings.pmtiles
shade/canopy.pmtiles                  # only where redistribution is approved
shade/horizon-<cell>.zst
map/israel-basemap.pmtiles            # downloadable regions, not embedded whole
reports/validation.json
reports/licenses.spdx.json
```

`manifest.json` MUST include:

- artifact schema versions and SHA-256 hashes;
- exact input hashes and observation/service dates;
- the product coverage polygon and per-cell N/S/V tiers;
- feature counts, topology statistics, validation results, and known gaps;
- attribution text, source URLs, licenses, and redistribution decisions;
- routing-engine and cost-model versions;
- build workflow commit and reproducible build parameters.

The deployment pins the manifest digest, downloads artifacts into a staging
directory, verifies all hashes and schemas, warms each engine, runs smoke routes,
and then atomically switches the active manifest. A failed check leaves the
previous manifest serving. Request handlers never observe a mixed release.

### Build workflow

1. **Acquire.** Download sources in CI or a dedicated data builder. Preserve raw
   inputs by hash and reject partial or unexpectedly old files.
2. **Normalize.** Preserve WGS84 source geometry, use EPSG:2039 where appropriate,
   and use a per-cell local metric frame for shadow geometry. Normalize Hebrew,
   Arabic, and English names without discarding original tags.
3. **Conflate conservatively.** OSM remains the topology spine. Alternative
   footprints or heights may fill a gap only when spatial/semantic match rules
   pass; provenance and uncertainty remain attached to each feature.
4. **Build topology.** Produce turn-aware road graphs, mode-specific access,
   logical signalized intersections, explicit sidewalk sides, legal crossings,
   the search index, and transit tables.
5. **Build shade data.** Convert building parts into attributed 2.5-D prisms,
   sample eligible sidewalk center/left/right positions every 3-5 m, and compute
   directional horizon profiles in qualified urban cells.
6. **Validate.** Reject broken references, implausible coordinates/heights,
   disconnected critical networks, duplicate signal clusters, illegal turns,
   missing attribution, large unexplained count regressions, and incompatible
   schemas.
7. **Publish.** Write the manifest last, sign or checksum it, and publish immutable
   objects. Never overwrite an existing digest.

Horizon profiles SHOULD initially use 5-degree azimuth buckets with quantized
elevation and an error bound recorded by the builder. The builder MUST benchmark
2-, 5-, and 10-degree variants against exact ray tests before locking the storage
format. Nationwide cells without enough source quality remain S0/S1 rather than
incurring multi-gigabyte horizon storage with misleading precision.

### Side-aware pedestrian topology

- Explicit `footway=sidewalk` geometry is highest-confidence.
- Left/right offsets derived from a road centerline require width/side evidence,
  collision checks against buildings/barriers, and a confidence downgrade.
- Side changes are edges, not geometric snaps. Normal routes may cross only at
  mapped or validated legal crossings.
- Inferred crossings are a separately flagged experimental graph layer and MUST
  never contribute to S2/S3 claims.
- Route geometry MUST follow the selected sidewalk side. A centerline polyline
  with a side label does not satisfy the 3D navigation requirement.

## Routing optimality contract

### Meaning of optimal

For request `q`, snapshot `D`, cost-model version `C`, and departure/arrival time
`t`, a result is optimal only over the feasible paths encoded by `(D, C, t)`.
Feasibility applies access, direction, turn, vehicle, crossing, boarding, and user
accessibility constraints before preference ranking.

Every alternative MUST contain:

```text
policy
objective_vector
hard_constraints
constraint_slack
dominance_reason
dataset_version
cost_model_version
data_confidence
freshness
fallback_reason
```

After the policy objective vector is equal, deterministic tie-breaking is
distance, stable edge/leg identifiers, then encoded geometry. The same request
and manifest MUST reproduce the same normalized result. Search timeouts may
return a declared bounded result but MUST NOT call it globally optimal.

### Compare-all response semantics

`POST /v1/routes/plan` SHOULD default to `comparison=all_applicable`. The API
calculates all relevant policies for the chosen mode and returns a stable set:

- walk: Fastest, Balanced Shade, Maximum Shade;
- car/motorcycle/truck: Fastest, Fewer Lights;
- bicycle/scooter: Fastest, Safer Streets, Combine Transit where applicable;
- transit: Fastest, Fewer Transfers, and allowed vehicle combinations.

Unsupported, dominated, or materially identical policies are omitted with a
machine-readable reason. Geometric alternatives with excessive overlap are
deduplicated, but a materially different tradeoff is preserved. The mobile UI
may recommend one card but MUST show the comparable set without asking the user
to choose a preference first.

### Fastest street route

Fastest minimizes modeled generalized travel time under all hard constraints.
Bidirectional landmark A* is valid only with an admissible heuristic for the
active cost model. CI MUST compare A* cost against Dijkstra on sampled subgraphs,
restriction patterns, and modes. Base and historical speeds must be labeled as
modeled. No live road-traffic language is allowed until a source, freshness rule,
and field-calibration gate are added.

### Fewer traffic lights

Signals are clustered into logical signalized intersections so multi-node OSM
representations are counted once. Let `F` be Fastest and candidate `P`:

```text
eta(P)      <= eta(F) * 1.10
distance(P) <= distance(F) * 1.15
signal_reduction(P) >= max(2, ceil(signal_count(F) * 0.20))
```

Among feasible low-signal candidates, minimize `(logical_signal_count, eta,
distance)` lexicographically. If none satisfies every inequality, omit the card
and return `no_material_low_signal_alternative`; do not relabel Fastest. The card
shows total logical signals on every road alternative, not only the number
avoided. Signal completeness is part of route confidence.

### Shade routes

Shade search is time-dependent and side-aware. A label contains at least:

```text
(node, sidewalk_side, crossing_state, arrival_time,
 expected_sun_exposure_seconds, exposure_upper_bound_seconds,
 unknown_exposure_seconds)
```

Dominance is component-wise over arrival and exposure after matching discrete
state. The fastest walking duration is calculated first:

- Balanced Shade: `duration <= fastest_duration * 1.15`;
- Maximum Shade: `duration <= fastest_duration * 1.30`.

Within each cap, the default risk-aware ranking minimizes exposure upper bound,
then expected exposure, unknown exposure, and arrival time. The implementation
MUST retain a bounded Pareto frontier; it MUST NOT hide the detour constraints
inside an arbitrary scalar weight or reward missing data. Edge exposure uses
solar position at predicted edge-arrival time. If the time-dependent cost
violates the FIFO property, the engine switches to a validated label-correcting
algorithm rather than relying on A* assumptions.

Reported metrics are observed/modelled shade percentage, high-confidence shade
percentage, sun-exposure minutes, detour, crossing count, and tier distribution.
Percentages use traversed distance and MUST not count unknown samples as shaded.

### Transit and vehicle combinations

The bounded Range-RAPTOR state is `(stop, round, vehicle_state)`. The Pareto
vector covers arrival time, transfers, walking, riding, carry distance,
stairs/elevators, schedule reliability, and rental freshness. Operator rules are
effective-dated hard constraints. Unknown bicycle/scooter permission is never
silently recommended. Shared vehicles are returned before boarding and a new
post-transit rental is independently selected and revalidated.

SIRI-SM observations, when credentials exist, are normalized into a small
internal prediction contract keyed to the pinned GTFS service. The adapter MUST
handle dated trip identifiers, cancellations, stale/out-of-order messages, and
prediction monotonicity. Without a fresh observation the itinerary remains
explicitly scheduled.

## 3D shade rendering architecture

### Two calculations, one source model

Routing and rendering share the same attributed 2.5-D building/canopy model but
serve different representations:

- **Routing:** compact horizon samples answer whether each side-aware route
  sample sees the sun at its predicted arrival time.
- **Rendering:** projected ground polygons show shadows at one selected clock
  time. The active route's shade pattern still represents arrival-time exposure,
  so a long route can legitimately differ from the single-time scene.

This distinction MUST be visible in the legend/time control. It prevents a map
of "shadows now" from being misread as the exposure along a 45-minute walk.

### Scene model

Each building part has a footprint `P`, base height `b`, top height `h` above the
local ground plane, source, observation date, and confidence. Height precedence is measured/licensed height,
OSM `height`, OSM building-part height, `building:levels` converted using a
documented regional prior, external attributed height, then a visibly estimated
default. A default height can produce S1/V2 geometry but never S2/S3 confidence.

Use the [NREL Solar Position Algorithm](https://midcdmz.nrel.gov/spa/) accuracy
as the solar reference, with explicit `Asia/Jerusalem` timezone conversion and
UTC instants. At solar elevation `e > 0`, a point at height `z` is projected onto
the local ground opposite solar azimuth by:

```text
offset(z) = -sun_horizontal_unit_vector * z / tan(e)
lower_offset = offset(b)
upper_offset = offset(h)
```

For every prism, compute the swept footprint between `translate(P, lower_offset)`
and `translate(P, upper_offset)`. This correctly handles elevated building parts
with `min_height > 0`; a ground-based part has `b = 0`. Union overlapping parts,
preserve holes where valid, clip to the requested corridor/view, repair invalid
polygons deterministically, and simplify only within a recorded
screen-space/metre error. At `e <= 0`, the UI switches to night state instead of
generating unbounded polygons. Canopy is a separate semi-transparent occlusion
layer with seasonal transmittance and confidence; it is not merged into opaque
building shade.

The result is exact for vertical 2.5-D prisms on the selected local plane. Terrain
correction, non-flat roofs, balconies, and translucent vegetation require richer
inputs and are part of V3, not silently approximated as exact reality.

### Server and artifact contract

The route response contains a small descriptor, never a duplicated national
polygon payload:

```json
{
  "shade_scene": {
    "scene_id": "sha256:...",
    "model_version": "...",
    "coverage_tier": "V2",
    "route_corridor_m": 500,
    "valid_from": "...",
    "valid_until": "...",
    "current_url": "...",
    "next_url": "...",
    "building_tiles": "pmtiles://...",
    "attribution": ["..."]
  }
}
```

A shade-scene service reads memory-mapped building/canopy indexes, calculates
polygons for 60-second UTC buckets, and caches by `(manifest, cells, bucket,
LOD)`. The client prefetches current and next buckets for the visible route
corridor and cross-fades between them; it does not geometrically interpolate
invalid polygons. Preview time scrubbing requests the selected bucket. Active
navigation refreshes after a bucket change, material camera movement, or route
change, never faster than the device/network budget.

For offline continuation the route package contains route geometry, maneuvers,
arrival-time shade annotations, buildings for the downloaded corridor, and a
bounded sequence of scene buckets. V2 ground shadows freeze at the last prefetched
bucket when that sequence expires and the UI falls back to the route annotation.
A later native C++/JSI prism projector may enable fully dynamic offline V2, but it
cannot be a launch dependency before parity and crash testing pass.

### Mobile renderer

MapLibre React Native/Native owns the camera, basemap, route, building
`fill-extrusion`, and ground-shadow fill layers. Global `light` is synchronized
to sun azimuth/elevation only to make building facets legible; it is cosmetic and
MUST NOT be treated as cast shade. [MapLibre's building-layer example](https://maplibre.org/maplibre-native/android/examples/styling/building-layer/)
demonstrates extrusion, while the open [cast-shadow style proposal](https://github.com/maplibre/maplibre-style-spec/issues/1797)
confirms that projected building shadows are not currently a standard native
style capability.

Layer order is basemap, ground shadows, sidewalks/crossings, route casing, route
shade/sun pattern, maneuver/handoff markers, 3D buildings, then navigation HUD.
The route must remain readable against both light and dark shadows and must use
pattern as well as color. Preview defaults to a north-aware 45-60 degree pitch;
active guidance offers heading-up 3D and an immediate 2D overview. Reduced-motion,
screen-reader, thermal-pressure, and low-memory states fall back to V0/V1 without
affecting routing.

The experimental [MapLibre GL JS building-shadows plugin](https://github.com/wallabyway/maplibre-building-shadows)
may be used only as a visual benchmark in a WebGL2 spike. It is not a React
Native production dependency and a WebView is not the primary navigation map.

### 3D performance and correctness gates

- Compare projected polygons with an independent reference implementation for
  1,000 generated footprints, concavities, holes, building parts, low-sun cases,
  and timezone/DST boundaries.
- Field-check at least 30 walks in each S3 candidate region across morning,
  noon, afternoon, and two seasons. High-confidence shade/sun classification
  must reach at least 85%.
- On the designated mid-tier Android and oldest supported iPhone, route preview
  and navigation must keep 95th-percentile frame time at or below 33.3 ms during
  the standard dense-urban trace, without OS memory termination.
- Warm current/next corridor scene generation must meet a measured p95 budget
  before rollout. The initial target is one second for a 500 m route corridor;
  if it fails, reduce LOD/corridor or precompute rather than hiding latency.
- The one-hour navigation battery gate remains under 12%; enabling 3D must not
  regress the reference-device result by more than three percentage points.
- Golden screenshots cover RTL/LTR, day/night, missing height, S1 versus S3,
  time scrub, offline expiry, and 2D accessibility fallback.

## Operational sizing and deployment

### Profiles

| Profile | Components | Honest use |
| --- | --- | --- |
| Local/CI | Data builder, compact fixture, emulator | Deterministic development and correctness checks |
| $0 showcase | Render Free gateway plus immutable artifacts and explicitly rate-limited community/provider adapters | Single-user demonstrations; cold starts, no SLA, no nationwide production claim |
| Nationwide beta | Separate gateway, memory-mapped Valhalla, compact RAPTOR or OTP, search, and shade-scene worker | Public testing after measured load/field gates |
| Scale | Replicated private routing services, object/CDN artifact delivery, observability, staged manifest rollout | Sustained public traffic and engine failover |

[Render Free](https://render.com/docs/free) sleeps after inactivity and is not
recommended by Render for production. Its current 512 MB/0.1 CPU shape cannot
host a credible nationwide Valhalla, transit graph, search index, and shade
worker in one process. [OTP keeps its graph in memory](https://docs.opentripplanner.org/en/latest/System-Requirements/)
and documents deployments from under 1 GB to over 100 GB, so a national OTP size
must be measured, not guessed.

Provisioning starts from CI measurements, not fixed marketing numbers:

1. Record compressed/uncompressed artifact size, cold/warm RSS, page faults,
   startup time, route p50/p95/p99, and concurrency saturation for every manifest.
2. Allocate at least 30% memory headroom above measured p99 RSS and enough disk
   for active plus rollback manifests.
3. As an initial benchmark shape, test Valhalla at 2 GB RAM, the compact RAPTOR
   service at 1-2 GB, OTP at 4 GB, and the shade worker at 2 GB/2 CPU. These are
   test points, not production guarantees; move upward when the measurements say
   so.
4. Keep the FastAPI gateway stateless and small. Engine health/readiness includes
   the loaded manifest digest, not merely an open TCP port.
5. Never silently fall back from a failed live provider to fixtures. Degraded
   output carries an explicit freshness/fallback code.

Use [Cloudflare R2](https://developers.cloudflare.com/r2/pricing/) or equivalent
object storage for immutable artifacts and region/corridor PMTiles. R2's free
tier can help early artifact distribution, but quotas and operations are still
monitored. Do not place a whole-country basemap in the APK. Users download named
regions or active-route corridors; MapLibre Native can read local PMTiles, but
[PMTiles is not an offline-pack cache source](https://maplibre.org/maplibre-native/android/examples/data/PMTiles/),
so the archive itself must be downloaded and versioned.

SIRI deployment requires legitimate Ministry access. The official onboarding
form requests network details/static addressing; shared Render outbound ranges
must not be assumed acceptable. If a dedicated egress IP is required, it is a
paid infrastructure dependency and scheduled-only transit remains the fallback.

## Delivery stages and release gates

| Stage | Concrete output | Gate to continue |
| --- | --- | --- |
| 0. Contract and legal inventory | Accepted API/optimality ADR, coverage polygon, source registry, license decisions, benchmark corpus | No unresolved public-redistribution blocker in the base national bundle |
| 1. National bundle | OSM graph, GTFS/RAPTOR, search, signals, manifest, reports, rollback loader | Clean topology/license checks and reproducible build from pinned raw hashes |
| 2. Nationwide N1 | Search and compare-all routing for every supported mode; scheduled transit; no fixture fallback | Nationwide golden corpus and load targets pass on measured deployment shape |
| 3. Data-qualified policies | Logical signals, vehicle restrictions, safer-street inputs, SIRI-SM adapter if authorized | Caps/rules hold for every golden case; stale/out-of-order feed tests pass |
| 4. Side-aware shade pilot | S2 sidewalk graph and horizon bundles for 3-5 representative cities | Crossing/legal invariants and 85% high-confidence field shade gate pass |
| 5. V2 3D pilot | Extrusions, projected scene service, time scrub, corridor cache, offline fallback | Geometry, device performance, accessibility, RTL/LTR, thermal, and battery gates pass |
| 6. Progressive expansion | Per-cell S2/S3/V2 activation through manifest flags | Each region independently satisfies data and field gates; rollback exercised |

The nationwide golden corpus contains at least 2,000 pinned origin/destination/time
scenarios distributed across districts, dense and sparse settlements, intercity
roads, ferry/rail/bus boundaries where relevant, mode restrictions, DST/service
date edges, and coverage-boundary cases. In addition:

- A* cost equals Dijkstra on a statistically meaningful sample of subgraphs and
  every restriction regression fixture.
- Every route is connected and respects one-way, turn, access, truck, vehicle,
  crossing, and transit boarding constraints.
- Low-signal cards satisfy all three advertised inequalities for 100% of the
  golden corpus.
- Shade cards satisfy the selected detour cap for 100% of the golden corpus and
  never classify unknown exposure as shade.
- GTFS tests cover service exceptions, `24+` hour times, timezone/DST, transfers,
  and date changes. SIRI tests cover cancellation, stale/out-of-order messages,
  missing trip matches, and fallback to schedule.
- Field validation includes at least Jerusalem, Haifa, Be'er Sheva, Eilat, one
  northern Arab locality, one Sharon/coastal city, and the Tel Aviv metro before
  broad N3/S3 language is used.

## License and source controls

The table below is a technical release checklist, not legal advice. Legal review
must resolve ambiguous publisher terms.

| Source/component | Constraint |
| --- | --- |
| [OpenStreetMap copyright/ODbL](https://www.openstreetmap.org/copyright) | Show `© OpenStreetMap contributors`, link ODbL, record derived-database obligations, and make required derived database offers available |
| Geofabrik extract | Preserve OSM/Geofabrik attribution metadata and obey automated-download guidance |
| Ministry GTFS | Record the exact government source/terms and snapshot; do not imply real-time service |
| Ministry SIRI | Credentials and interface terms are deployment secrets/conditions; never publish keys or raw retained observations outside approved terms |
| National canopy | `Other (Open)` is insufficiently precise for automated redistribution; quarantine until a named license/approval is recorded |
| [Overture attribution](https://docs.overturemaps.org/attribution/) | Preserve feature provenance, ODbL attribution, and applicable notice files |
| [OpenFreeMap](https://openfreemap.org/) | Keep visible OSM/provider attribution; public service has no SLA, so maintain a PMTiles/self-host fallback |
| MapLibre and all code dependencies | Generate SPDX SBOM from package metadata and audit actual versions; do not rely on this document as the license source |
| Municipal/GBFS sources | Store provider, license, attribution, observation time, deep link, and redistribution scope per adapter |

CI fails when a public artifact contains an unknown license, missing attribution,
an expired approval, or source data outside its permitted geographic/purpose
scope.

## Risk register

| Risk/trigger | Mitigation | Release consequence |
| --- | --- | --- |
| Incomplete/missing heights or canopy | Provenance-aware merge, estimated ranges, field sampling, per-cell S tiers | Stay S0/S1; no Maximum Shade verification claim |
| Missing sidewalks or legal crossings | Explicit side graph first, conservative offsets, no nearest-side snap | Fall back to Fastest or experimental route with explicit warning |
| No free nationwide live road traffic | Baseline/historical cost model and precise copy | Do not claim Waze/Google live ETA parity |
| OSM restriction/signal incompleteness | Logical clustering, completeness metrics, golden/field audits | Downgrade N2 confidence or omit policy |
| GTFS/SIRI mismatch or stale messages | Snapshot-aware normalizer, staleness thresholds, schedule fallback | Label scheduled; do not use unmatched predictions |
| Ambiguous canopy/municipal license | Quarantine layer and legal registry | Artifact publishes without that source; tier drops |
| MapLibre Native lacks cast shadows | Naviz-generated polygon layer and V0/V1 fallback | No shademap-like ground-shadow claim before V2 gate |
| Terrain/roof geometry error | Local-plane disclosure, slope confidence penalty, later DEM ADR | V2 model-exact only; V3 withheld |
| National artifact/mobile storage growth | Cell partitioning, memory mapping, regional/corridor downloads, LOD | No whole-country map/shade package in APK |
| Free compute cold start/OOM | Separate services, measured sizing/headroom, readiness and atomic rollback | $0 remains showcase, not public-production profile |
| Static egress required for SIRI | Confirm Ministry network requirements before architecture purchase | Scheduled transit until legitimate access exists |
| Boundary/name sensitivity | Explicit technical coverage polygon and locale-reviewed labels | No coverage inferred from third-party extract naming |

## Reasoning-effort guidance: Ultra versus High

Ultra is justified for the present architecture phase and for the small set of
work where a subtle error changes route legality, user safety, truthfulness, or
release licensing. It does not make missing source data accurate and should not
be spent on routine UI implementation.

| Work | Effort | Why |
| --- | --- | --- |
| Optimality/Pareto contract, admissibility/FIFO proof, side/crossing legality | **Ultra** | Cross-module invariants and silent correctness failures |
| Shade geometry, solar/time semantics, confidence model, native 3D design | **Ultra** | Numerical, geospatial, temporal, and device constraints interact |
| Source licensing/provenance and nationwide release audit | **Ultra** | One bad decision can block redistribution or invalidate claims |
| Architecture/security/privacy ADR and launch go/no-go review | **Ultra** | Irreversible public-interface and safety implications |
| Implementing a locked adapter, pipeline step, API model, or React Native screen | **High** | Complex senior engineering, but bounded by an accepted contract |
| Tests and fixtures for an already specified invariant | **High** | Breadth and rigor matter; semantics are already decided |
| Copy/layout polish and routine refactors after design approval | **High** | Requires quality and device validation, not architecture re-derivation |

Recommended workflow: use Ultra now to approve this contract, resolve sources,
and design the V2 spike; then use High for parallel implementation work. Return
to Ultra for routing/shadow review, anomalous field results, and each regional or
public release gate. Medium/low effort is inappropriate for safety-relevant route
logic.

## Primary references

- [Valhalla overview](https://valhalla.github.io/valhalla/) and
  [tile architecture](https://valhalla.github.io/valhalla/tiles/)
- [OpenTripPlanner data sources](https://docs.opentripplanner.org/en/latest/Data-Sources/),
  [system requirements](https://docs.opentripplanner.org/en/latest/System-Requirements/),
  and [supported SIRI adapters](https://docs.opentripplanner.org/en/latest/SIRI-Config/)
- [Official Ministry developer information](https://www.gov.il/he/Departments/Topics/developer_information)
  and [SIRI access form](https://www.gov.il/BlobFolder/generalpage/real_time_information_siri/he/real_time_information_receipt_form.pdf)
- [CoolWalks time-dependent shade-routing paper](https://arxiv.org/abs/2405.01225)
- [OSM explicit sidewalk](https://wiki.openstreetmap.org/wiki/Tag%3Afootway%3Dsidewalk),
  [continuous crossing](https://wiki.openstreetmap.org/wiki/Key%3Acrossing%3Acontinuous),
  and [building-level semantics](https://wiki.openstreetmap.org/wiki/Key%3Abuilding%3Alevels)
- [MapLibre React Native setup/native versions](https://maplibre.org/maplibre-react-native/docs/setup/getting-started/)
  and [RasterDEM source limitations](https://maplibre.org/maplibre-react-native/docs/components/sources/raster-dem-source/)
- [OpenFreeMap terms](https://openfreemap.org/tos/)
