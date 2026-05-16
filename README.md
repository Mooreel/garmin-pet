# Codex Pet for Garmin

Codex Pet is a local-first Garmin Connect IQ app that shows your latest Codex activity on a Garmin watch with an animated pet, task overview, task details, and a browser-based build pipeline.

The goal of this repo is that a Mac user can clone it, run one setup script, start one local server, and build a watch app without manually wiring bridge ports or editing config files.

## Quick Start

```bash
git clone https://github.com/Mooreel/garmin-pet.git
cd garmin-pet
scripts/setup_mac.sh
scripts/start.sh
```

Open the local pipeline:

```text
http://127.0.0.1:8790
```

Then use the browser flow:

1. Connect your Garmin watch over USB.
2. Import a pet from Petdex or drop a local pet ZIP/folder.
3. Pick your watch target and theme.
4. Run security check.
5. Click Save & build app.
6. Click Deploy latest PRG.
7. Unplug the watch so Garmin can ingest the sideloaded app.

## Requirements

| Requirement | Why it is needed | Setup script |
| --- | --- | --- |
| macOS | Current build/deploy scripts target Mac paths and launch services. | Checks only |
| Python 3 | Runs the local pipeline server and setup tooling. | Checks only |
| Pillow Python package | Exports Petdex/local pet spritesheets into Garmin PNG frames. | Installs into `.venv` |
| Garmin Connect IQ SDK Manager | Provides `monkeyc` and device SDKs for building the PRG. | Checks only |
| JDK | Required by Garmin `monkeyc`. | Can install OpenJDK with `--install-deps` if Homebrew exists |
| Garmin watch | Needed for deploy and real-device testing. | Auto-detects in the web UI |
| Garmin Connect on iPhone | Carries watch web requests to the local bridge. | Manual |
| Same WiFi/LAN for Mac and iPhone | The watch bridge runs on your Mac. | Auto-generates the LAN URL |
| Optional `libmtp` | Helps deploy to watches that do not mount as USB storage. | Can install with `--install-deps` if Homebrew exists |

Garmin SDK Manager itself is not installed automatically because it is a licensed Garmin desktop tool. Install it from Garmin, add an SDK, and make sure `monkeyc` is on PATH or set `GARMIN_SDK_HOME`.

## What Setup Automates

Run:

```bash
scripts/setup_mac.sh
```

It safely creates local, git-ignored files:

- `.venv/`
- `bridge_token.txt`
- `pipeline/local.json`
- `pipeline/work/`
- `build/developer_key.der` when `openssl` is available

It also checks:

- Python 3
- Python packages from `requirements.txt`
- Garmin `monkeyc`
- Java / OpenJDK
- `libmtp` deploy tools
- generated watch bridge URL

To let the script install the Homebrew packages it can safely automate:

```bash
scripts/setup_mac.sh --install-deps
```

That may install:

- `openjdk`
- `libmtp`

It will not install Garmin SDK Manager automatically.

## One Server, One Port

Start the pipeline:

```bash
scripts/start.sh
```

The browser UI is:

```text
http://127.0.0.1:8790
```

The watch bridge is served by the same process and port:

```text
http://<mac-lan-ip>:8790/garmin/latest?token=<local-token>
```

You do not need to configure a second bridge server. The pipeline detects the Mac LAN address, creates a token, and injects the correct bridge URL when you save/build.

## Optional Always-on Synology Bridge

If you do not want the Mac pipeline server running all day, host only the watch bridge on a Synology NAS:

```bash
scripts/synology/deploy_bridge.sh
```

That starts a small Python bridge on the Synology and updates local builds to use:

```text
http://synology.local:8790/garmin/latest?token=<local-token>
```

The Mac is still needed for pet import, preview, Garmin SDK builds, and USB deploy. The NAS only keeps the watch endpoint available. After using Codex on the Mac, publish the latest payload to the NAS:

```bash
scripts/synology/publish_payload.sh
```

For a custom `pet.local` URL, make sure `pet.local` resolves on your LAN through router DNS or an mDNS/Bonjour alias, then deploy with:

```bash
GARMIN_PUBLIC_BRIDGE_HOST=pet.local scripts/synology/deploy_bridge.sh
```

See [docs/SYNOLOGY_BRIDGE.md](docs/SYNOLOGY_BRIDGE.md) for the full setup and reboot notes.

On Nico's Synology setup, `pet.local` is published through a small mDNS alias
process and the browser dashboard is available at:

```text
http://pet.local:8790/
```

## Build From The Browser

Use the web UI at `http://127.0.0.1:8790`.

Recommended flow:

1. Confirm the watch banner says the Garmin watch is accessible.
2. Import a pet from Petdex or drop a ZIP/folder with `pet.json` and `spritesheet.webp`.
3. Preview the pet home, task list, and task detail screens in the watch frame.
4. Run security check.
5. Click Save & build app.
6. Deploy latest PRG.

The security check is required before build because this project creates local tokens and keys that must never be committed.

## Build From The Terminal

```bash
python3 scripts/configured_build.py --config pipeline/local.json --device fr265s
```

Deploy the last build:

```bash
scripts/install_to_watch.sh
```

The generated app lives at:

```text
build/CodexPet.prg
```

## Keep It Running

For a persistent local server:

```bash
scripts/install_pipeline_launch_agent.sh
```

This installs a user LaunchAgent that runs the unified pipeline server on port `8790`.

## Project Structure

```text
pipeline/                 Local web app, API, Petdex import, bridge endpoint
pipeline/app/bridge.py    Garmin payload, token, LAN URL, /garmin/latest route
pipeline/web/preview.js   Browser watch-screen simulator
source/                   Monkey C Garmin app
config/devices.json       Extendable watch device registry
resources/images/         Generated pet frames
scripts/                  Setup, start, build, deploy, validation helpers
docs/                     Extra quickstart and troubleshooting notes
```

## Add Another Watch

1. Add the watch profile to `config/devices.json`.
2. Add the real frame image under `pipeline/web/assets/devices/`.
3. Set the screen size, shape, and frame screen rectangle.
4. Keep `buildEnabled: false` until the Garmin target is in `manifest.xml`.
5. Run:

```bash
python3 scripts/configured_build.py --config pipeline/local.json --device <device-id>
```

Only set `buildEnabled: true` after the build works for that device.

## Add Or Replace A Pet

Use the browser importer, or prepare a folder/ZIP with:

```text
pet.json
spritesheet.webp
```

The pipeline exports the frames into `resources/images/` for the Garmin app.

## Before Committing

Run:

```bash
python3 scripts/security_check.py
python3 scripts/validate_project.py
```

`security_check.py` fails if tracked files contain local tokens, private keys, developer keys, local certificates, or build artifacts.

## Troubleshooting

If the watch shows `Bridge -300`, the phone/watch path timed out reaching your Mac.

Check:

- `scripts/start.sh` is running.
- The app was rebuilt after setup or network changes.
- The bridge URL shown in the UI uses port `8790`.
- The iPhone and Mac are on the same LAN.
- Garmin Connect has Local Network permission in iOS Settings.
- macOS firewall allows Python/local network access.

More detail is in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
