# Adding Your Existing Docs & Swagger Endpoints to Backstage

Two ways to do this: **quick manual registration** (good for the demo, no repo changes) and **catalog-info.yaml in the repo** (the real, scalable way). Start with the first to see it work fast, then move to the second for anything permanent.

---

## Option A — Quick manual registration (no repo changes, 2 minutes)

With `yarn dev` running:

1. Go to `http://localhost:3000/catalog-import`
2. Paste a URL to a `catalog-info.yaml` file — it doesn't have to exist yet in the repo. You can host one anywhere (even a gist) and point at it.
3. Click **Analyze**, then **Import**.

This is the fastest way to demo "here's our API" without touching the actual service repo yet. Skip to Option B once you're onboarding for real.

---

## Option B — Add `catalog-info.yaml` to the repo (recommended)

### 1. Register your existing Swagger/OpenAPI spec

You don't need to move or duplicate your spec file — point Backstage at wherever it already lives.

**If the spec is a file in the same repo:**
```yaml
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: orders-api
  description: Orders service REST API
spec:
  type: openapi
  lifecycle: production
  owner: team-orders
  definition:
    $text: ./openapi.yaml      # relative path in the same repo
```

**If the spec is served live (e.g. `/v3/api-docs` from Springdoc, or a hosted swagger.json):**
```yaml
spec:
  type: openapi
  lifecycle: production
  owner: team-orders
  definition:
    $text: https://orders-api.yourdomain.com/v3/api-docs
```

**If the spec lives in a different repo than the service:**
```yaml
spec:
  type: openapi
  lifecycle: production
  owner: team-orders
  definition:
    $text: https://raw.githubusercontent.com/YOUR_ORG/api-specs/main/orders/openapi.yaml
```

Any of these renders a full Swagger UI page automatically once imported — no plugin install needed, `type: openapi` is built in.

### 2. Link the API to its Component (the service that owns it)

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: orders-service
  description: Orders microservice
  annotations:
    github.com/project-slug: YOUR_ORG/orders-service
spec:
  type: service
  lifecycle: production
  owner: team-orders
  providesApis: [orders-api]
---
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: orders-api
spec:
  type: openapi
  lifecycle: production
  owner: team-orders
  definition:
    $text: ./openapi.yaml
```

Put both in `catalog-info.yaml` at the repo root (`---` separates multiple entities in one file).

### 3. Add existing docs (TechDocs)

TechDocs uses **MkDocs** under the hood. If you already have markdown docs, you mostly just need to point at them — no rewriting required.

**If you don't have an `mkdocs.yml` yet**, add one at the repo root:
```yaml
# mkdocs.yml
site_name: 'Orders Service'
nav:
  - Home: index.md
  - Architecture: architecture.md
plugins:
  - techdocs-core
```

Put your existing markdown files in a `docs/` folder (create it if needed, move existing `.md` files in — they don't need reformatting, standard markdown works as-is):
```
orders-service/
├── catalog-info.yaml
├── mkdocs.yml
├── openapi.yaml
└── docs/
    ├── index.md
    ├── architecture.md
    └── ... (your existing docs, just moved/copied here)
```

**Annotate the Component** to tell Backstage where the docs are:
```yaml
metadata:
  name: orders-service
  annotations:
    github.com/project-slug: YOUR_ORG/orders-service
    backstage.io/techdocs-ref: dir:.     # "docs are in this same repo, root-relative"
```

If your docs live in a *different* repo from the code:
```yaml
annotations:
  backstage.io/techdocs-ref: url:https://github.com/YOUR_ORG/docs-repo/tree/main
```

### 4. Preview TechDocs locally before pushing (optional but useful for the demo)

```bash
# from inside the repo with mkdocs.yml
npx @techdocs/cli generate --no-docker
npx @techdocs/cli serve
```
This builds and serves the docs exactly as Backstage would render them, at `http://localhost:8000`, without needing the full Backstage app running.

---

## 5. Point your dev environment at these repos

Back in your Backstage app's `app-config.local.yaml`, either list repos individually:

```yaml
catalog:
  locations:
    - type: url
      target: https://github.com/YOUR_ORG/orders-service/blob/main/catalog-info.yaml
    - type: url
      target: https://github.com/YOUR_ORG/payments-service/blob/main/catalog-info.yaml
```

or auto-discover everything with `catalog-info.yaml` across the org (better once you have more than a handful):

```yaml
catalog:
  locations:
    - type: github-discovery
      target: https://github.com/YOUR_ORG/*/blob/-/catalog-info.yaml
```

Restart `yarn dev` (or wait — the catalog polls on an interval; default is 100s min) and the new services, APIs, and docs will appear in the catalog automatically.

---

## Quick copy-paste: minimal working example

Drop this at the root of any existing repo, adjust names/paths, done:

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: my-service
  annotations:
    github.com/project-slug: YOUR_ORG/my-service
    backstage.io/techdocs-ref: dir:.
spec:
  type: service
  lifecycle: production
  owner: my-team
  providesApis: [my-service-api]
---
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: my-service-api
spec:
  type: openapi
  lifecycle: production
  owner: my-team
  definition:
    $text: ./openapi.yaml
```

Then import it via `http://localhost:3000/catalog-import` pointing at the raw GitHub URL of that file — that's the whole flow.
