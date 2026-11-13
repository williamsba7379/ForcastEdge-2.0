# Read-only 2026 NFL Weeks 8–9 historical reconciliation candidate

**Research-only, not an archive update or model input.** The existing historical-results archive contains zero Week 8 and zero Week 9 games. The source schedule in this repository contains only Weeks 10 and 11, so independent ESPN/NFL game IDs and kickoff timestamps have NOT been established here. Do not import these candidates until IDs, dates, final status and score provenance are independently confirmed for every row. `UNVERIFIED` is intentional; no fabricated IDs.

Sources for comparison: NFL official Week 8 https://www.nfl.com/schedules/2026/by-week/week-8 and Week 9 https://www.nfl.com/schedules/2026/by-week/week-9 ; independent CBS Week 8 https://www.cbssports.com/nfl/schedule/2026/regular/8/ and Week 9 https://www.cbssports.com/nfl/scoreboard/9/2026/regular/9/ . These are reference URLs, not captured immutable source payloads.

| Week | Away | Home | Away final | Home final | Verified game ID | Archive | Provenance gate |
|---|---|---|---:|---:|---|---|---|
| 8 | Carolina | Green Bay | 19 | 27 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Atlanta | Tampa Bay | 0 | 16 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Arizona | Dallas | 33 | 30 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Baltimore | Buffalo | 10 | 36 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Cleveland | Pittsburgh | 6 | 27 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Indianapolis | Jacksonville | 7 | 42 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Las Vegas | NY Jets | 38 | 33 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Minnesota | Detroit | 15 | 19 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Tennessee | Cincinnati | 36 | 43 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | LA Chargers | LA Rams | 9 | 24 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Kansas City | Denver | 24 | 28 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | New England | Miami | 24 | 19 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Philadelphia | Washington | 10 | 27 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 8 | Chicago | Seattle | 34 | 17 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Jacksonville | Baltimore | 33 | 10 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Cincinnati | Atlanta | 34 | 17 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Cleveland | New Orleans | 22 | 23 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Dallas | Indianapolis | 27 | 23 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Denver | Carolina | 26 | 21 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Detroit | Miami | 19 | 9 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | LA Rams | Washington | 20 | 13 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | NY Giants | Philadelphia | 19 | 11 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | NY Jets | Kansas City | 12 | 35 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Houston | LA Chargers | 44 | 22 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Arizona | Seattle | 3 | 17 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Green Bay | New England | 45 | 27 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Las Vegas | San Francisco | 17 | 38 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Tampa Bay | Chicago | 24 | 27 | UNVERIFIED | MISSING | PENDING_ID_MATCH |
| 9 | Buffalo | Minnesota | 23 | 6 | UNVERIFIED | MISSING | PENDING_ID_MATCH |

## Conflict handling

The 29 candidate scores match the consulted official NFL schedule pages and secondary score listings at the matchup/score level. **This is not a game-ID-based match** until the game IDs are sourced and reconciled against a separately captured complete scoreboard. Any disagreement in ID, team mapping, final status, kickoff or scores must produce `BLOCKED_CONFLICT` and no writes. Jacksonville–Baltimore Week 9 should receive explicit second-source confirmation because an earlier secondary listing was reported inconsistent. Do not assert absence of all conflicts until complete game-level provenance exists.

## Required next step

Capture immutable, timestamped complete ESPN scoreboard responses for weeks 8 and 9 plus official NFL schedule evidence; normalize event IDs, UTC kickoffs, final status and scores; compare every event ID against the original archive; emit read-only `MISSING`, `MATCH`, `CONFLICT` classifications. Preserve all original archive bytes.
