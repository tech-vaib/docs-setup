# Backstage on a Single Azure VM — Complete Setup

**Scope covered:** software catalog, GitHub repo integration, Swagger/OpenAPI pages, TechDocs, local PostgreSQL on the same VM, and a login mode you can flip on/off (Guest vs GitHub OAuth) via one env var. Sized for a small internal user base (dozens, not thousands).

---

## 1. Architecture (single-VM, small team)

```
┌─────────────────────────────────────────────┐
│  Azure VM (Ubuntu 22.04, Standard_B2ms/B4ms) │
│                                               │
│  ┌───────────┐   ┌──────────────┐            │
│  │  Nginx    │──▶│ Backstage    │            │
│  │  :443/:80 │   │ (Node, :7007)│            │
│  └───────────┘   └──────┬───────┘            │
│                          │                    │
│                  ┌───────▼───────┐            │
│                  │ PostgreSQL 15 │            │
│                  │ (localhost)   │            │
│                  └───────────────┘            │
└─────────────────────────────────────────────┘
```

Yes — one VM is fine for a small user base. Backstage's frontend + backend + Postgres all comfortably fit on a **B2ms (2 vCPU/8GB)**; go **B4ms (4 vCPU/16GB)** if you'll index many repos/TechDocs or expect >30 concurrent users. Keep Postgres on the same VM (localhost socket) — no need for Azure Database for PostgreSQL at this scale, though you can migrate to it later since Backstage just needs a connection string.

---

## 2. Azure VM provisioning

```bash
# From Azure CLI (run locally or in Cloud Shell)
az group create -n backstage-rg -l eastus

az vm create \
  -g backstage-rg \
  -n backstage-vm \
  --image Ubuntu2204 \
  --size Standard_B2ms \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard

# Open the ports you need: 22 (SSH), 80/443 (web)
az vm open-port -g backstage-rg -n backstage-vm --port 80 --priority 1010
az vm open-port -g backstage-rg -n backstage-vm --port 443 --priority 1020
# Do NOT open 7007 or 5432 publicly — they stay behind Nginx / localhost only
```

SSH in:
```bash
ssh azureuser@<vm-public-ip>
```

---

## 3. Base packages: Node.js, PostgreSQL, Nginx, Docker (optional)

```bash
sudo apt update && sudo apt upgrade -y

# Node 20 LTS (Backstage requires Node 18 or 20)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v   # confirm v20.x

# Yarn (Backstage's package manager)
sudo corepack enable
corepack prepare yarn@stable --activate

# PostgreSQL
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

# Nginx (reverse proxy + TLS termination)
sudo apt install -y nginx certbot python3-certbot-nginx

# git (for TechDocs/catalog to clone repos)
sudo apt install -y git build-essential python3
```

---

## 4. PostgreSQL local setup

```bash
sudo -u postgres psql <<'EOF'
CREATE ROLE backstage WITH LOGIN PASSWORD 'change-me-strong-password';
ALTER ROLE backstage CREATEDB;
EOF
```

Backstage creates its own databases per-plugin automatically on first boot (catalog, auth, scaffolder, etc.) as long as the role has `CREATEDB`. No manual schema needed.

Lock Postgres to localhost only (default on Ubuntu install, just confirm):
```bash
sudo grep -n "listen_addresses" /etc/postgresql/*/main/postgresql.conf
# should be: listen_addresses = 'localhost'
```

---

## 5. Create the Backstage app

```bash
mkdir -p /opt/backstage && sudo chown $USER:$USER /opt/backstage
cd /opt/backstage

npx @backstage/create-app@latest --path .
# When prompted, name it e.g. "internal-portal"
```

This scaffolds `packages/app` (frontend) and `packages/backend`.

---

## 6. app-config.yaml — Postgres, GitHub integration, TechDocs, auth toggle

Edit `/opt/backstage/app-config.yaml`:

```yaml
app:
  title: Internal Developer Portal
  baseUrl: https://portal.yourdomain.com

organization:
  name: YourOrg

backend:
  baseUrl: https://portal.yourdomain.com
  listen:
    port: 7007
    host: 0.0.0.0
  csp:
    connect-src: ["'self'", 'http:', 'https:']
  cors:
    origin: https://portal.yourdomain.com
    methods: [GET, POST, PUT, DELETE]
    credentials: true
  database:
    client: pg
    connection:
      host: 127.0.0.1
      port: 5432
      user: backstage
      password: ${POSTGRES_PASSWORD}

integrations:
  github:
    - host: github.com
      token: ${GITHUB_TOKEN}   # PAT with repo/read:org scope, for catalog discovery

# ---- AUTH TOGGLE ----
# Set AUTH_DISABLE_LOGIN=true in the env to run with no login (guest only).
# Set it to false (or unset) to require GitHub OAuth sign-in.
auth:
  disableLogin: ${AUTH_DISABLE_LOGIN}
  environment: production
  providers:
    guest: {}
    github:
      production:
        clientId: ${AUTH_GITHUB_CLIENT_ID}
        clientSecret: ${AUTH_GITHUB_CLIENT_SECRET}

techdocs:
  builder: local          # builds docs on the VM itself; fine for small teams
  generator:
    runIn: local
  publisher:
    type: local            # stores generated docs on local disk
                            # switch to 'awsS3'/'azureBlobStorage' later if you outgrow local disk

catalog:
  import:
    entityFilename: catalog-info.yaml
    pullRequestBranchName: backstage-integration
  rules:
    - allow: [Component, System, API, Resource, Location, Group, User]
  locations:
    # Point at repos containing catalog-info.yaml. Add one entry per repo,
    # or use the GitHub org discovery processor below to auto-discover.
    - type: github-discovery
      target: https://github.com/YOUR_ORG/*/blob/-/catalog-info.yaml

# Swagger/OpenAPI pages come from the API entities discovered above (type: openapi)
# — no extra plugin config needed beyond the catalog + integrations.github block.
```

Create `app-config.production.yaml` for prod-only overrides if desired (optional, can skip for a single-VM setup).

---

## 7. Environment variables

Create `/opt/backstage/.env` (never commit this):

```bash
POSTGRES_PASSWORD=change-me-strong-password
GITHUB_TOKEN=ghp_your_read_only_pat
AUTH_GITHUB_CLIENT_ID=your_oauth_app_client_id
AUTH_GITHUB_CLIENT_SECRET=your_oauth_app_client_secret

# The toggle: "true" = no-login/guest mode, "false" = GitHub OAuth required
AUTH_DISABLE_LOGIN=true
```

GitHub OAuth App setup (only needed if you'll use `AUTH_DISABLE_LOGIN=false`):
1. GitHub → Settings → Developer settings → OAuth Apps → New OAuth App
2. Homepage URL: `https://portal.yourdomain.com`
3. Authorization callback URL: `https://portal.yourdomain.com/api/auth/github/handler/frame`

---

## 8. Wire the auth toggle into the frontend

Edit `packages/app/src/App.tsx`. Replace the default `createApp` config with:

```tsx
import { githubAuthApiRef, configApiRef, useApi } from '@backstage/core-plugin-api';
import { SignInPage } from '@backstage/core-components';

const app = createApp({
  apis,
  bindRoutes({ bind }) {
    // ...existing bindRoutes content stays as-is
  },
  components: {
    SignInPage: props => {
      const configApi = useApi(configApiRef);
      const disableLogin = configApi.getOptionalBoolean('auth.disableLogin') ?? false;

      if (disableLogin) {
        return <SignInPage {...props} auto providers={['guest']} />;
      }

      return (
        <SignInPage
          {...props}
          provider={{
            id: 'github-auth-provider',
            title: 'GitHub',
            message: 'Sign in using GitHub',
            apiRef: githubAuthApiRef,
          }}
        />
      );
    },
  },
});
```

And in `packages/backend/src/index.ts` (or `plugins/auth.ts` if you're on the older backend system), allow the guest provider to run outside development mode, since you're intentionally using it in prod when the toggle is on:

```ts
backend.add(import('@backstage/plugin-auth-backend'));
backend.add(import('@backstage/plugin-auth-backend-module-guest-provider'));
backend.add(import('@backstage/plugin-auth-backend-module-github-provider'));
```

The `guest-provider` module works out of the box for local/dev; for it to be usable in a "production" NODE_ENV on your VM, keep `NODE_ENV` set to whatever you're comfortable with — many teams just run Backstage with `NODE_ENV=development` semantics on internal-only VMs specifically to allow guest auth safely, since the portal isn't internet-facing to the public. If you want guest auth allowed under a true production NODE_ENV, the guest module accepts a `dangerouslyAllowOutsideDevelopment: true` resolver option — only set this if the VM is genuinely restricted to trusted internal users (e.g. behind a VPN, or you're intentionally running with `AUTH_DISABLE_LOGIN=true` for a closed pilot group).

---

## 9. Build and do a first run

```bash
cd /opt/backstage
set -a; source .env; set +a

yarn install
yarn tsc
yarn build:backend

# quick smoke test
yarn start
# Ctrl+C once you confirm http://localhost:7007 loads
```

---

## 10. systemd service (so it survives reboots/crashes)

```bash
sudo tee /etc/systemd/system/backstage.service > /dev/null <<'EOF'
[Unit]
Description=Backstage Developer Portal
After=network.target postgresql.service

[Service]
Type=simple
User=azureuser
WorkingDirectory=/opt/backstage
EnvironmentFile=/opt/backstage/.env
ExecStart=/usr/bin/node packages/backend/dist/index.cjs.js --config app-config.yaml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now backstage
sudo systemctl status backstage
```

Flip the login mode any time by editing `.env` (`AUTH_DISABLE_LOGIN=true|false`) and running:
```bash
sudo systemctl restart backstage
```

---

## 11. Nginx reverse proxy + HTTPS

```nginx
# /etc/nginx/sites-available/backstage
server {
    listen 80;
    server_name portal.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:7007;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/backstage /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Free TLS cert (point your DNS A record at the VM's public IP first)
sudo certbot --nginx -d portal.yourdomain.com
```

---

## 12. Adding repos: catalog-info.yaml + Swagger/OpenAPI

In each repo you want cataloged, add a `catalog-info.yaml` at the root:

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: my-service
  description: My service description
  annotations:
    github.com/project-slug: YOUR_ORG/my-service
    backstage.io/techdocs-ref: dir:.
spec:
  type: service
  lifecycle: production
  owner: team-a
  providesApis: [my-service-api]
---
apiVersion: backstage.io/v1alpha1
kind: API
metadata:
  name: my-service-api
spec:
  type: openapi
  lifecycle: production
  owner: team-a
  definition:
    $text: https://raw.githubusercontent.com/YOUR_ORG/my-service/main/openapi.yaml
```

That `API` entity with `type: openapi` is what renders the Swagger UI page automatically in Backstage — no extra plugin install needed.

For TechDocs, add `mkdocs.yml` + a `docs/` folder to the repo; the `github-discovery` location in `app-config.yaml` will pick both up automatically once the repo has `catalog-info.yaml`.

---

## 13. Quick checklist

- [ ] VM provisioned, only 22/80/443 open publicly
- [ ] Postgres running, bound to localhost, `backstage` role created
- [ ] `.env` populated (Postgres password, GitHub token, OAuth creds, `AUTH_DISABLE_LOGIN`)
- [ ] `app-config.yaml` has your domain, github-discovery target updated to your org
- [ ] `App.tsx` sign-in toggle wired in
- [ ] `systemctl status backstage` → active
- [ ] Nginx + certbot → `https://portal.yourdomain.com` loads
- [ ] Test repo has `catalog-info.yaml` + shows up in the catalog

---

## Notes / things to revisit as you grow

- **Local disk TechDocs** is fine to start; if the VM is ever resized/replaced, back up `/opt/backstage` (specifically the TechDocs storage dir) or move to Azure Blob Storage as the publisher.
- **Postgres backups**: since it's local-only, set up a daily `pg_dump` cron job to a separate storage location (Azure Blob/Files) — a single VM has no redundancy.
- **Secrets**: `.env` on disk is fine for a small internal pilot; if this becomes org-wide, migrate secrets to Azure Key Vault and inject at service start instead.
- **Guest auth in "production"**: the `dangerouslyAllowOutsideDevelopment` flag is named that way for a reason — only use it when the VM's network exposure is genuinely restricted to people you trust.
