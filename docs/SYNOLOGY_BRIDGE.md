# Always-on Synology bridge

The Synology bridge keeps the Garmin watch endpoint online without keeping the
Mac pipeline server running all day.

It does not replace the Mac for every task:

- The Mac pipeline is still used for pet import, preview, Garmin SDK builds, and USB deploy.
- The Synology bridge serves the watch-facing `/garmin/latest` payload.
- Publish from the Mac whenever you want the NAS bridge to pick up the latest Codex activity.

## Deploy to Synology

Requirements:

- SSH access to the Synology as a user that can write to `/volume1/homes/nico/development`.
- Python 3 on the Synology.

Run from the repo root:

```bash
scripts/synology/deploy_bridge.sh
```

Defaults:

```text
Synology SSH host: synology
Synology directory: /volume1/homes/nico/development/garmin-pet-bridge
Bridge port: 8790
Public host embedded into Garmin builds: synology.local
mDNS browser alias: pet.local -> 192.168.0.246
```

Override them when needed:

```bash
GARMIN_SYNOLOGY_HOST=synology \
GARMIN_PUBLIC_BRIDGE_HOST=pet.local \
GARMIN_BRIDGE_PORT=8790 \
scripts/synology/deploy_bridge.sh
```

The script copies the small bridge server, publishes the current payload, starts
the Synology process, and updates `pipeline/local.json` so future builds use the
NAS bridge URL.

It also starts a lightweight mDNS alias publisher for `pet.local`. Opening
`http://pet.local/` lands on Synology Web Station, which redirects to the bridge
dashboard at `http://pet.local:8790/`.

## Publish updates

After the bridge is deployed, publish the latest local Codex payload with:

```bash
scripts/synology/publish_payload.sh
```

This is fast and does not require the browser pipeline server to be running.

## Start and stop on the NAS

The deploy script starts the bridge as a user process. To manage it manually:

```bash
ssh synology /volume1/homes/nico/development/garmin-pet-bridge/start_bridge.sh
ssh synology /volume1/homes/nico/development/garmin-pet-bridge/stop_bridge.sh
```

To make it survive Synology reboots, add this command in DSM Task Scheduler as a
boot-up user-defined script:

```bash
/volume1/homes/nico/development/garmin-pet-bridge/start_bridge.sh
```

## `pet.local`

The bridge can listen on all Synology network interfaces, but `pet.local` must
resolve on the LAN before a watch or phone can use it.

Good options:

- Use the included user-space mDNS alias publisher started by `deploy_bridge.sh`.
- Add `pet.local` as a local DNS record or alias in the router.
- Add an mDNS/Bonjour alias on the Synology if you manage Avahi as admin.
- Use `synology.local` as the public bridge host if you want the zero-admin setup.

Validate from the Mac:

```bash
dscacheutil -q host -a name pet.local
curl --max-time 5 http://pet.local:8790/health
```

If `pet.local` does not resolve, rebuild with `GARMIN_PUBLIC_BRIDGE_HOST=synology.local`
or add the LAN DNS alias first.
