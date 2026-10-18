# Link catalogue (checked 2026-10-18)

Read code with `curl -s https://raw.githubusercontent.com/<owner>/<repo>/HEAD/<path>`
and list files with the anonymous GitHub API
(`/repos/<owner>/<repo>/git/trees/HEAD?recursive=1`, parse with
`json.loads(..., strict=False)`; 60 requests/hour). `gh` may not be installed.

## Official Habbo
| What | Link | Notes |
|---|---|---|
| Web API docs (Swagger) | https://www.habbo.com/api/public/api-docs/#/ | bot-protected for scripts (HTTP 463); open in a browser |
| Sandbox docs | https://sandbox.habbo.com/api/public/api-docs/#/Wired%20Variables | test hotel "S2" |
| Variables explorer | https://wired.habbo.com/variables-explorer | official app; uses bigint JSON |

## WIRED Web API wrappers (MIT)
| Repo | Package |
|---|---|
| https://github.com/Habbo-API-Wrappers/Habbo-API-Wrapper-Python | https://pypi.org/project/wired-api-python/ (0.1.4) |
| https://github.com/Habbo-API-Wrappers/Habbo-API-Wrapper-Node | https://www.npmjs.com/package/wired-api-wrapper-node (1.0.6) |
| https://github.com/Habbo-API-Wrappers/Habbo-API-Wrapper-PHP | https://packagist.org/packages/wiredspast/habbo-api-wrapper-php (v1.0.2) |

| https://github.com/Habbo-API-Wrappers/Habbo-API-Wrapper-Go | `go get github.com/alynva/Habbo-API-Wrapper-Go` (Go 1.24+, stdlib HTTP, optional Bubble Tea TUI; README in Portuguese) |

Useful files: `src/wired_api_python/resources/variables/*.py`,
`.../datatypes/variables/*.py`, `.../addon/level_up.py` (has the max_xp bug),
Node `src/resources/variables/*.ts`, `src/http/transporter.ts`.

## Community projects using the WIRED Web API (found 2026-10-18)

Found by GitHub repo search (name/description only; anonymous code search isn't
available, so projects that only mention the API in code are missing). The API is
new, so expect these to change quickly. Check the last push before copying anything.

**Apps**
| Repo | What | Stack | Worth reading for |
|---|---|---|---|
| https://github.com/Habbodan/wired (live: wired.habbodan.com) | Web portal: paste a room's keys, browse/edit variables and profiles, bulk delete, any hotel, 9 languages | React 19, Vite, Tailwind 4, TanStack Query; Express 5, Prisma 7, MySQL | Browser calls the hotel directly with a client-side per-room rate limiter; keys in `sessionStorage` unless "remember" is ticked; saved keys AES-256-GCM encrypted and bound to owner + workspace; optional OAuth (PKCE). Read its limiter for real rate limit numbers |
| https://github.com/AnaBeatrizJBSan/docs-wired-club-statistics | Shows statistics of a GitHub docs repo inside a Habbo room | TypeScript | Pushing outside data into room variables |
| https://github.com/juanjovelezc/habbo-wired-dashboard | Dashboard (no README yet, pushed 2026-10-15) | JavaScript | Unknown; check before relying on it |

**Libraries (besides the official wrappers)**
| Repo | Package | Notes |
|---|---|---|
| https://github.com/michyaraque/habbo-sdk | npm `habbo-sdk` 0.6.0 | TypeScript, Node 22+ (global `fetch`); resources `profiles`, `variables`, `origins`; one `RoomInstance` per room bound to its keys |
| https://github.com/EjercitoFAM/habbo-api | `@ejercito-fam/habbo-api` | Typed TypeScript, values as `bigint`, `client.wired.room(id, {readKey, writeKey})`, Result-style `.unwrap()` |
| https://github.com/HabboFeelingNL/laravel-habbo-web-api | Packagist `habbofeelingnl/laravel-habbo-web-api` | Laravel 10-13, PHP 8.1+, typed DTOs, per-hotel domains; `HabboAuthException` (401/403), `HabboRateLimitException` (429, `retryAfter()`). Its README says the add-on was beta-only, which is now outdated |

## G-Earth ecosystem

Moved to the `habbo-gearth` skill: `habbo-gearth/references/repos.md` (sibling folder)
(G-Earth, frameworks, HabboPackets, Sulek, G-ExtensionStore).

## Extension side

For G-Earth extensions (and a tested G-Python template whose tests fake G-Earth), see
the `habbo-gearth` skill.
