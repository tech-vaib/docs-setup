# Backstage — Local Setup on macOS (Demo / Management Walkthrough)

Zero external services required. Uses the built-in SQLite database, so there's nothing to install or configure beyond Node and Backstage itself.

---

## 0. Why a database at all, and does it really use SQLite automatically?

**Yes, automatically.** When you scaffold a new app, the generated `app-config.yaml` ships with:

```yaml
backend:
  database:
    client: better-sqlite3
    connection: ':memory:'
```

No Postgres, no Docker, nothing to run separately — the backend just works on first `yarn start`.

**What the DB is actually for:** Backstage's backend isn't stateless — it persists the software catalog (services, APIs, systems you onboard), auth sessions, scaffolder/template run history, TechDocs build metadata, and permission rules. All storage goes through Knex, which is why the database is swappable via config, not code.

**`:memory:` vs a file:** `:memory:` resets everything on every restart — fine for a live demo since there's nothing to clean up between runs. If you want data to persist across restarts (e.g. you're demoing over a few days), change one line:

```yaml
backend:
  database:
    client: better-sqlite3
    connection: ${PWD}/backstage.sqlite
```

**Moving to Postgres/VM later:** point `app-config.yaml` at Postgres and restart — Backstage runs its own migrations and creates fresh tables automatically. Catalog data isn't manually migrated; it's *re-discovered* from GitHub (that's the point of the `github-discovery` integration), so it reappears on its own. Only things like scaffolder run history and stored sessions wouldn't carry over automatically — if you need those preserved, a tool like `pgloader` can move the raw SQLite data into Postgres, but most teams just accept a clean slate at that cutover.

---

## 1. Prerequisites install (Terminal)

```bash
# Homebrew, if you don't already have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Node 20 LTS (Backstage requires Node 18 or 20 — not 22+)
brew install nvm
mkdir -p ~/.nvm
echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.zshrc
echo '[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"' >> ~/.zshrc
source ~/.zshrc

nvm install 20
nvm use 20
node -v    # confirm v20.x.x

# Yarn via Corepack (ships with Node)
corepack enable
corepack prepare yarn@stable --activate
yarn -v

# git (usually already present on macOS; installs Xcode CLT if not)
git --version
```

---

## 2. Scaffold the app

```bash
mkdir -p ~/dev && cd ~/dev

npx @backstage/create-app@latest --path internal-portal
cd internal-portal
```

You'll be prompted for an app name — this becomes the folder/package name (e.g. `internal-portal`).

---

## 3. Project structure (what you'll get)

```
internal-portal/
├── app-config.yaml              # main config: DB, auth, integrations, catalog rules
├── app-config.local.yaml        # local-only overrides (gitignored)
├── package.json
├── packages/
│   ├── app/                     # React frontend
│   │   └── src/
│   │       ├── App.tsx          # sign-in page / auth wiring lives here
│   │       ├── components/
│   │       └── apis.ts
│   └── backend/                 # Node backend
│       └── src/
│           └── index.ts         # backend plugin registration (auth, catalog, techdocs...)
├── plugins/                     # (empty initially) custom plugins go here
├── examples/
│   ├── entities.yaml             # sample catalog entities
│   ├── org.yaml                  # sample org/team structure
│   └── template/                 # sample scaffolder template
└── catalog-info.yaml             # this repo's own catalog entry
```

Nothing to add for SQLite — `app-config.yaml` already has it configured out of the box (Section 0 above).

---

## 4. Minimal config for a demo (GitHub integration, optional)

If you want to show the catalog pulling in real repos during the demo, add a **read-only** GitHub token. Otherwise skip this — the app runs fine with just the sample `examples/entities.yaml` data.

Create a Personal Access Token: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained token, read-only on the repos/org you want to show.

```bash
# in the project root
touch app-config.local.yaml
```

```yaml
# app-config.local.yaml (gitignored automatically by the template — safe for secrets)
integrations:
  github:
    - host: github.com
      token: ghp_your_read_only_token_here

catalog:
  locations:
    - type: github-discovery
      target: https://github.com/YOUR_ORG/*/blob/-/catalog-info.yaml
```

`app-config.local.yaml` is merged on top of `app-config.yaml` automatically and is already in `.gitignore` — safe place for local secrets.

---

## 5. Run it

```bash
yarn install
yarn dev
```

This starts both frontend (port 3000) and backend (port 7007) and opens `http://localhost:3000` automatically. First install can take a few minutes; subsequent `yarn dev` runs are fast.

Sign-in: by default the template ships with **guest sign-in enabled**, so for a demo you just click through — no OAuth setup needed at all unless you specifically want to show off the GitHub-login flow too.

---

## 6. (Optional) Show the GitHub-login toggle in the demo

Same mechanism as the VM setup — one config flag controls it. In `app-config.local.yaml`:

```yaml
auth:
  disableLogin: false   # true = guest-only, false = require GitHub OAuth
  providers:
    guest: {}
    github:
      development:
        clientId: ${AUTH_GITHUB_CLIENT_ID}
        clientSecret: ${AUTH_GITHUB_CLIENT_SECRET}
```

Export the OAuth app credentials before starting (GitHub OAuth App with callback `http://localhost:3000/api/auth/github/handler/frame`):

```bash
export AUTH_GITHUB_CLIENT_ID=your_client_id
export AUTH_GITHUB_CLIENT_SECRET=your_client_secret
yarn dev
```

---

## 7. What to point out to management

- **Time to first running instance**: ~10–15 minutes, no infrastructure provisioned.
- **No DB server to stand up** for a demo — SQLite is bundled and automatic.
- **Same config surface scales to production** — the only thing that changes going from this Mac demo to the Azure VM setup is the `backend.database` block (SQLite → Postgres) and flipping `auth.disableLogin` to `false`. Everything else (catalog, TechDocs, Swagger pages, plugins) is identical.
- **Catalog is git-backed** — onboarding a team's service is just adding a `catalog-info.yaml` to their repo; nothing to manually enter into Backstage.

---

## 8. Quick copy-paste block (all commands, start to finish)

```bash
# Prereqs
brew install nvm
mkdir -p ~/.nvm
echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.zshrc
echo '[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"' >> ~/.zshrc
source ~/.zshrc
nvm install 20 && nvm use 20
corepack enable && corepack prepare yarn@stable --activate

# Scaffold
mkdir -p ~/dev && cd ~/dev
npx @backstage/create-app@latest --path internal-portal
cd internal-portal

# Run (SQLite in-memory, guest auth — zero config needed)
yarn install
yarn dev
```
