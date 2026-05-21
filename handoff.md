# Sales Territory Mapping Tool — Engineering Handoff
**Status:** Discovery complete, build approved pending scope confirmation
**Target delivery:** End of May 2026 (June reassignment deadline)
**Document owner:** [add your name]
**Last updated:** May 16, 2026
---
## 1. Background
The sales organization is restructuring from channel-vertical to market-based coverage. Regional Presidents (RPs) and Regional Sales Directors (RSDs) have been tasked with assigning every account out of each DC/Market to 2-3 sellers, geographically. The reassignments need to be executed in **June 2026**.
The current workaround is Google My Maps. It hits two hard limits:
1. **Line/row cap.** Southern California alone needs three separate maps to fit one market's accounts. RSDs can't see the full picture, which defeats the point of mapping in the first place.
2. **No filtering by business attributes.** They want to see Tire Pros status, Activate flag, Primary/Secondary Program, and TTM Volume while drawing territory lines. Google My Maps can't filter on these.
Christian (RP) walked through the workflow on the discovery call. Cynthia (sales ops) maintains the master Excel and currently uploads slices to Google Maps. The downstream output is an updated Excel with the new seller assignment per account.
This is **intermittent use** — likely every 6-12 months going forward, not daily. That informs the build-vs-buy decision: a lightweight internal tool fits the actual usage pattern better than a $75/user/month SaaS subscription.
---
## 2. What we're building
A single-page web app that lets one RSD at a time:
- Upload Cynthia's Excel file
- See every account in a market on one map, color-coded by currently-assigned seller
- Filter the visible pins by Tire Pros, Activate, Primary/Secondary Program, and TTM Volume range
- Click a pin to see account details and change the assigned seller via dropdown
- Box/lasso-select multiple pins and bulk-reassign to one seller
- See a per-seller summary in the sidebar (account count, total TTM volume) so they can balance territories
- Export an updated Excel that preserves the original column structure plus a `new_seller` column
Out of scope for v1 (explicitly): multi-user real-time editing, saved/named scenarios, audit trail, auth/permissions, drive-time routing, demographic overlays, drawn-polygon auto-assignment, mobile, SalesInsights API integration.
---
## 3. Tech stack
All open-source, no paid subscriptions.
| Layer | Tool | Why |
|---|---|---|
| Frontend framework | React + Vite | Fast scaffold, standard tooling |
| Map rendering | MapLibre GL JS | Open-source fork of Mapbox GL, no API key required |
| Map tiles | OpenStreetMap public tile server | Free for internal/intermittent use; self-host later if needed |
| Geocoding | US Census Geocoder (batch) | Free, no key, no rate limit, US-only — perfect fit |
| Selection tools | mapbox-gl-draw + Turf.js | Lasso/box drawing + point-in-polygon |
| Clustering | MapLibre built-in cluster layer | Handles tens of thousands of points |
| Excel I/O | SheetJS Community Edition | Reads and writes .xlsx in browser |
| State | React useState/useReducer | No backend in v1, no Redux needed |
| Hosting | Internal static file server or nginx container | One static bundle, no server-side code |
No database, no backend server, no auth in v1. The Excel file is the source of truth in and out.
---
## 4. Data flow
```
┌──────────────────┐    ┌────────────────────────┐    ┌──────────────┐
│ Cynthia's Excel  │ -> │ One-time geocoding via │ -> │ Excel with   │
│ (no lat/long)    │    │ US Census Geocoder     │    │ lat/long     │
└──────────────────┘    └────────────────────────┘    └──────┬───────┘
                                                             │
                                                             v
                                            ┌───────────────────────────────┐
                                            │ Browser app                   │
                                            │ - Upload                      │
                                            │ - Plot on map                 │
                                            │ - Filter, click-reassign      │
                                            │ - Lasso bulk-reassign         │
                                            │ - Export updated Excel        │
                                            └───────────────┬───────────────┘
                                                            │
                                                            v
                                                ┌────────────────────────┐
                                                │ Updated Excel with     │
                                                │ new_seller column      │
                                                └────────────────────────┘
```
Geocoding is a one-time preprocessing pass. Don't geocode at runtime in the app — it's slow and unnecessary. Run a Python script against Cynthia's file, write lat/long columns, re-save. Cache the result.
---
## 5. Expected input data structure
From the discovery transcript, Cynthia's Excel contains roughly:
| Column | Type | Notes |
|---|---|---|
| Account Name | string | Required |
| Customer Number | string | Required, unique |
| Address | string | Required for geocoding |
| City | string | Required for geocoding |
| State | string | Required for geocoding |
| Zip | string | Required for geocoding |
| Suggested Seller | string | Current assignment |
| MTD Sales | number | For sidebar totals |
| YTD Sales | number | For sidebar totals |
| TTM Volume | number | Filter range |
| Tire Pros | boolean | Filter checkbox |
| Activate | boolean | Filter checkbox |
| Primary Program | string | Filter dropdown |
| Secondary Program | string | Filter dropdown |
| Market | string | For multi-market files |
| DC | string | For multi-market files |
**Action item before coding:** Get the actual file from Cynthia. Confirm exact column names, data types, and any fields not listed here. Build a sample dataset for development that matches the real schema.
**Output columns added by the app:**
| Column | Type | Notes |
|---|---|---|
| New Seller | string | Updated assignment |
| Assignment Changed | boolean | Flag for rows the RSD modified |
| Assigned At | timestamp | When the change was made |
Preserve all original columns in the output. Sales ops downstream processes likely depend on the existing structure.
---
## 6. Build plan and time estimates
Single developer with AI coding assistance, focused work. Estimates assume Cynthia's real Excel is available by Day 1.
| Day | Deliverable |
|---|---|
| 1 | Scaffold React/Vite app, install dependencies, integrate MapLibre with OSM tiles, render empty map |
| 1 | Write geocoding script (Python + US Census batch endpoint), geocode Cynthia's sample file, validate hit rate |
| 2 | SheetJS upload + parse, plot pins as GeoJSON, color by `Suggested Seller`, basic popup |
| 3 | Sidebar filter panel: seller multi-select, Tire Pros, Activate, Primary/Secondary Program, TTM Volume slider |
| 3 | Per-seller summary panel (count, TTM total) that respects filters |
| 4 | Click pin -> change seller dropdown in popup, state updates, color updates in real time |
| 4 | mapbox-gl-draw integration for box and lasso select |
| 5 | Bulk reassign UI: select N pins, choose new seller from dropdown, apply |
| 5 | MapLibre clustering at lower zoom levels, un-cluster at street level |
| 6 | Excel export with full round-trip fidelity (preserve column order, formatting, formulas where possible) |
| 6 | "Review failed geocodes" panel — accounts that didn't geocode, with manual lat/long input |
| 7 | End-to-end test with real West region data (multi-DC file). Fix performance issues. |
| 7 | Polish: keyboard shortcuts, undo last change, confirm-before-export |
| 8 | User test with Cynthia on SoCal. Triage feedback. Ship. |
**Buffer:** Two days for IT/security review, unexpected data quality issues, and the inevitable "one more thing" from Cynthia. Total realistic window: **two weeks from kickoff**.
---
## 7. Critical risks and mitigations
### Geocoding accuracy
Tire-store addresses in strip malls, mall annexes, and shared lots geocode poorly. Expect **5-15% failure rate**.
**Mitigation:** Build the "review failures" UI on Day 6. Let Cynthia paste corrected lat/long or pick a point on the map manually. Cache her corrections so they survive future imports.
### Excel round-trip fidelity
If the export breaks Cynthia's downstream process, she rejects the tool no matter how good the map is.
**Mitigation:** Get a sample of the *downstream* file (whatever consumes her output) early. Test round-trip with the real file before showing it to her. SheetJS preserves most formatting but verify formulas, merged cells, and conditional formatting.
### Dense urban areas (Christian's "side of the street" problem)
In SoCal, two stores on opposite sides of one street may belong to different sellers. Overlapping pins at default zoom hide this.
**Mitigation:** Disable clustering above zoom level 15. Use pin offset / spiderfy for stacked pins. Make pin click hit-area generous. Test with the dense parts of LA before shipping.
### Performance at full West region scale
3 markets × 14 DCs = potentially 10K-50K pins. MapLibre handles this with clustering on, but un-clustered street-level rendering of thousands of pins can stutter.
**Mitigation:** Cluster aggressively at lower zooms. Limit un-clustered render to viewport + small buffer. If it stutters, switch to MapLibre's `symbol` layer with icon sprites instead of HTML markers.
### IT / security approval
An internal app that handles customer addresses and sales volume will trip data classification review at most companies.
**Mitigation:** Open the conversation with IT/security **on Day 1**, not Day 8. The code can be done in a week; the approval may not be. If approval looks like it'll slip past June, switch to a parallel Maptive 10-day trial as a safety net so Cynthia isn't blocked.
### Cynthia's existing workflow
She has muscle memory in Google My Maps. The transcript hints at specific friction ("you just see a box and you can't put it"). Don't assume — watch her use the current tool before finalizing UX.
**Mitigation:** Schedule a 30-minute screen-share with Cynthia before finalizing the v1 UX. Take notes on what she does instinctively. Mirror those gestures where possible.
---
## 8. Open questions for stakeholders
Resolve these in the early-next-week follow-up meeting Rahul promised Christian.
1. **Total row count across the full West region?** Drives clustering strategy and confirms geocoding scale.
2. **Does the Excel already include lat/long, or only addresses?** If yes, skip the geocoding step entirely.
3. **Who else besides Cynthia/Christian needs access?** Single user = no auth needed. Multiple = how do we control which markets each person sees?
4. **What downstream system consumes the updated Excel?** Determines export format requirements.
5. **Is concurrent editing required?** The transcript implies no. Confirm in writing — this is the single biggest scope decision.
6. **Hosting target?** Internal server, cloud VM, or static file host behind SSO? Affects IT review path.
7. **For v2 (post-June): is there appetite for PostGIS + a real backend?** This is the natural evolution; flag it now so it's on the roadmap.
---
## 9. v2 roadmap (post-June, only if usage justifies it)
If the v1 ships and people actually use it, the next iteration moves to a real backend. Don't build this until the v1 has been used through at least one reorg cycle and you know what's actually needed.
- **PostgreSQL + PostGIS** for persistence, scenarios, audit trail
- **Node/Express or Python/FastAPI** backend with REST API
- **Self-hosted Nominatim** for ongoing geocoding (replaces Census Geocoder, handles non-US if needed)
- **Self-hosted tile server** (TileServer GL + Geofabrik OSM extract) to eliminate the OSM public tile dependency
- **Named scenarios:** "June 2026 SoCal proposal v3", "current alignment", side-by-side compare
- **Audit trail:** who reassigned what, when, why
- **Auth:** company SSO, region-based access control
- **Polygon-based territory drawing** with auto-assignment via ST_Contains
- **Optional CRM/SalesInsights integration** to pull source data automatically instead of Excel import
The v1 data structures (account object with lat/long and seller_id) map 1:1 to the PostGIS schema, so this is an evolution, not a rewrite.
---
## 10. Reference: discovery call summary
Key points from the May discovery call with Christian, Cynthia, Biju, and Rahul:
- Sales reorg is moving from channel verticals to market-based coverage.
- RPs/RSDs are responsible for the assignment work; one RSD per market handles their own market's accounts.
- Current state: Google My Maps, three maps for SoCal because of row limits, master Excel maintained by Cynthia.
- They are **not** using it for routing or drive-time — purely a spatial view for assignment planning.
- They need relative-location awareness (highway corridors, freeway boundaries, side-of-street splits in dense urban areas).
- Time-sensitive: reassignments need to be executed in June 2026. If a custom tool takes weeks, they'll fall back to the Google Maps workaround.
- Frequency post-launch: intermittent, every 6-12 months, tied to revenue/quota changes.
---
## 11. Recommended first actions
For whoever owns the build:
1. **Today:** Email Cynthia to request the real master Excel (or a one-market subset). Ask for column names, row count, and a sample row.
2. **Today:** Open the IT/security conversation. State the tool's purpose, data handled, and target users. Get the review path documented.
3. **Day 1:** Geocode the sample with the US Census Geocoder. Measure hit rate. If it's below 85%, escalate — geocoding strategy may need a fallback (Nominatim, manual review queue, etc.).
4. **Day 1:** Scaffold the Vite project, get MapLibre rendering OSM tiles in the browser. Smallest possible "hello world" with a real map.
5. **End of Day 1:** Status update to Rahul/Biju with go/no-go on the May timeline.
---
*Questions or scope changes? Reach out to [your name] in Teams.*
