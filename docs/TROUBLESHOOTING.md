# Troubleshooting

## Watch Shows Bridge -300

`Bridge -300` means the phone/watch path timed out reaching the Mac.

Check:

- The pipeline server is running with `scripts/start.sh`.
- The watch app was rebuilt after the bridge URL changed.
- The bridge URL uses the Mac LAN IP and port `8790`, not `127.0.0.1`.
- The Mac and paired iPhone are on the same network.
- Garmin Connect has Local Network permission in iOS Settings.
- macOS firewall is not blocking Python on the local network.

Open the pipeline and check the generated bridge in the Setup panel. It should look like:

```text
http://192.168.x.x:8790/garmin/latest?token=...
```

The supported browser build flow injects that LAN URL automatically. If you run
`scripts/build.sh` directly while `source/CodexBuildConfig.mc` still contains a
loopback URL, the script now stops before creating a real-watch build that would
timeout with `Bridge -300`.

## Browser Loads But Watch Cannot Reach The Bridge

The browser can use `127.0.0.1`, but the watch cannot. The server must be reachable on the LAN. Start it with:

```bash
scripts/start.sh
```

That binds to `0.0.0.0:8790` and lets the UI inject a LAN bridge URL.

## Address Already In Use

If starting the server prints that port `8790` is already in use, the pipeline is usually already running.

Open:

```text
http://127.0.0.1:8790
```

To run a second copy for testing:

```bash
python3 pipeline/server.py --port 8791
```

## Security Check Blocks Build

The build intentionally requires the security check first. It prevents publishing local tokens, keys, certificates, or build products by mistake.

Run:

```bash
python3 scripts/security_check.py
```

Fix any reported tracked files before committing.

If you downloaded the GitHub ZIP instead of cloning with Git, the same command still works. In that mode it scans the project files directly and skips local-only folders such as `.venv`, `build`, and `pipeline/work`.

## Pet Import Fails With Missing Pillow

Run setup again:

```bash
scripts/setup_mac.sh
```

The setup script creates `.venv` and installs the Python packages from `requirements.txt`. Start the app with `scripts/start.sh` so the server uses that environment.

## Garmin Watch Not Detected

Reconnect USB and unlock/approve the watch connection if prompted. The pipeline checks both mounted Garmin storage and MTP.

If MTP is needed on macOS, install libmtp tools through Homebrew:

```bash
brew install libmtp
```

## Garmin SDK Not Found

Install Garmin Connect IQ SDK Manager and make sure `monkeyc` is on PATH, or place an SDK under:

```text
build/connectiq-sdk-9.1.0
```

Then rerun:

```bash
scripts/setup_mac.sh
```
