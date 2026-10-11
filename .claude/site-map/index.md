# Site map — index

Legend: ✅ verified live (date) · plain = read from code · ⚠ unconfirmed.
Read this file plus the area file(s) you are about to touch — never the whole
directory (`site-map` §0). Base URLs come from the active test-env file
`src/test/resources/env/<test.env>.yml`.

ONBOARD: seeded during `qa-core:onboard-new-project` stage 2 with the entry page, the
auth mechanism (from `login-strategies` step 1) and the locator strategy (does
the app expose `data-testid`/`data-qa`?); areas and their pages come later with
`add-page`, each widget noted with the standard element that handles it.

## <app name> — `base.url` = <url> (env `<env>`)

<stack in one line>. Locator strategy: <data-testid / id / classes>.
Auth: <cookie / token / header>, how tests get it (`auth/…`).

| Area | File | Covers | Updated |
|---|---|---|---|
| <area> | [<area>.md](<area>.md) | <pages, 1 line> | <YYYY-MM-DD> |

### App-wide gotchas

Only what holds across areas (auth, CSRF, a session-wide trap). Anything
page-specific lives in that page's area file.

### Not mapped yet

- <area / flow nobody has walked>

## Open questions
