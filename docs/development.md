# Development

## Requirements

- Python 3.12 (validated with 3.12.14 on Windows).
- Node 24 (validated with 24.19.0).
- pnpm 11.19.0, as recorded in frontend/package.json.

The frontend and backend are separate local processes. The Vite development and
preview servers proxy `/api` to `http://127.0.0.1:8000`, so browser requests use
the same origin. All servers bind to loopback. Hosting is not configured.

## Install

From the repository root in PowerShell, using a Python 3.12 executable:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
pnpm --dir frontend install --frozen-lockfile
```

Check `python --version` first. If `python` points to a different runtime, replace
it with the full path to Python 3.12. Do not install into a shared/global Python.
On this Codex host the bundled runtime can be selected with:

```powershell
$runtimeDir = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
& (Join-Path $runtimeDir 'python\python.exe') -m venv .venv
$pnpmPath = Join-Path $runtimeDir 'bin\fallback\pnpm.cmd'
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
& $pnpmPath --dir frontend install --frozen-lockfile
```

Registry access is needed for initial installation. Python transitive versions
are pinned in requirements.lock; frontend versions and transitives are pinned
in package.json/pnpm-lock.yaml. Use those files rather than installing latest
packages to reproduce this scaffold. The Python lock is the tested Windows
Python 3.12 environment, not a claim of validation on every OS.

## Run

Terminal 1, repository root:

```powershell
.\scripts\dev-backend.ps1
```

Terminal 2, repository root:

```powershell
.\scripts\dev-frontend.ps1
```

If pnpm is not on PATH, pass `-Pnpm` with its executable path (for example the
bundled `$pnpmPath` above). Both scripts run in the foreground; Ctrl+C stops
their process. If PowerShell script execution is restricted, use these commands:

```powershell
.\.venv\Scripts\python.exe -m uvicorn travel_agent.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
pnpm --dir frontend dev
```

Run those two commands in separate terminals. Open [the app](http://127.0.0.1:5173).
The page must show **Fixture demo**, **Trip commands** (without a model key), and
**Fixture service · no live bookings**. Select **Cheap weekend** for three synthetic
comparisons. Follow [the demo walkthrough](demo.md) for the full journey.
Click **Check connection** to repeat the browser-to-backend check.
[Health JSON](http://127.0.0.1:8000/api/health) and
[API documentation](http://127.0.0.1:8000/docs) are also available.

## Modes and credentials

Fixture mode is the default and requires no model or travel credentials.
Optionally copy backend/.env.example to backend/.env. It is ignored by Git and
loaded from a stable backend path regardless of working directory. Environment
variables override the file. Restart the backend after configuration changes.

`TRAVEL_DATA_MODE=live` reports `live_adapters_unavailable` until a hotel key and
positive call allowance are configured. Then it reports `hotel_search_configured`
and enables the Milwaukee hotel pilot. It never falls back to synthetic data.
See [hotel setup](hotel-setup.md) for boundaries and the pending live gate.
Fixture mode reports `planning_available=true` and `fixtures_ready`.

Natural-language chat is opt-in: see [model setup](model-setup.md). Without a model,
use commands and sample trips. Model/hotel adapters are implemented and tested with
controlled responses; authenticated validation remains pending. For no-provider
replay, use TRAVEL_DATA_MODE=fixture, TRAVEL_MODEL_PROVIDER=disabled,
TRAVEL_MODEL_MAX_CALLS=0 and TRAVEL_HOTEL_MAX_CALLS=0 (the example defaults).

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests -q
.\.venv\Scripts\python.exe -m pip check
pnpm --dir frontend build
pnpm --dir frontend test
```

The production build performs TypeScript checking. To inspect it locally, keep
the backend running and use `pnpm --dir frontend preview`, then open port 4173.
The generated frontend is not a standalone live deployment without a backend
and an `/api` routing configuration.

## Current boundaries

See [implementation architecture](implementation.md) and [evaluation](evaluation.md)
for current capabilities and pending live gates. Fixture destinations are provisional
scope, not verified offers. Trips disappear on restart; select **New trip** after an
expired-session message. Provider counts persist: see [reliability](reliability.md).
Run one worker. The local unauthenticated API is not ready for public hosting.

If connection fails, start both processes and check the health URL. Stop your old
instance if a port is occupied. After configuration changes, restart the backend and
select **Check connection**. A 409 requires reloading authoritative trip state.
Do not delete the usage database to retry an exhausted provider allowance.

See the [vault build log](<../../../../Obsidian Vault/2. Projects/Portfolio/Travel Agent/Dev Log/Travel Agent - Build Log.md>)
for evidence and the [loop plan](<../../../../Obsidian Vault/2. Projects/Portfolio/Travel Agent/Specs/Travel Agent - Build Loops.md>)
before implementing the next increment.

