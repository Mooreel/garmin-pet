# Quickstart

This project runs as one local web app. The browser pipeline and Garmin watch bridge share the same port.

## 1. Clone

```bash
git clone https://github.com/Mooreel/garmin-pet.git
cd garmin-pet
```

## 2. Prepare The Mac

```bash
scripts/setup_mac.sh
```

The setup script checks Python, Java, Garmin `monkeyc`, and MTP tools. It creates `.venv`, installs Python packages, creates the local bridge token, creates `pipeline/local.json`, and creates `build/developer_key.der` when possible.

For Homebrew-managed dependencies that can be automated:

```bash
scripts/setup_mac.sh --install-deps
```

This can install `openjdk` and `libmtp`. Garmin Connect IQ SDK Manager still needs to be installed manually from Garmin.

## 3. Start

```bash
scripts/start.sh
```

Open:

```text
http://127.0.0.1:8790
```

The watch bridge is served by the same process:

```text
http://<mac-lan-ip>:8790/garmin/latest?token=<local-token>
```

The UI generates this URL automatically during Save & build.

## 4. Build

In the browser:

1. Import a Petdex pet or drop a local pet ZIP/folder.
2. Choose the Garmin target.
3. Run security check.
4. Click Save & build app.

## 5. Deploy

Connect the watch over USB, wait for the banner to show accessible watch status, then click Deploy latest PRG.

After deploy, unplug the watch so Garmin can ingest the sideloaded app.
