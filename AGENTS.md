# Controlling a PS5 with chiaki-python

Use this repository for Remote Play controller input and H.264 screenshots. It works on a stock console before a jailbreak and remains available after a reboot. A payload-based tool such as PS5_DevLoop must be reloaded after each reboot; Chiaki does not need that payload.

## Safety and credentials

- Pair only consoles you own or have permission to control. Confirm the console and user before sending input.
- Look, press, then look again. Do not run long navigation scripts without checking screenshots between steps.
- Credentials live in `~/.config/Chiaki/Chiaki.conf` or in registration JSON files. Never print or commit them.
- Chiaki's verbose logs can contain registration keys, authentication headers, and tokens. Redirect logs to `captures/` and do not display them unless they have been sanitized.
- Keep generated profiles, scripts, screenshots, and logs under `captures/`; it is ignored by git.
- Do not change the saved console address just because it is stale. Use `CHIAKI_HOST` for the current address.

## Build

Clone recursively and build on the host:

```bash
git clone --recursive https://github.com/earthonion/chiaki-python.git
cd chiaki-python
./build.sh
```

The build creates `libchiaki.so`. On Debian/Ubuntu, missing `json-c` and `miniupnpc` development packages are downloaded and extracted under `.deps/` without sudo. Other systems need equivalent development files available before building.

The wrapper build is headless and LAN-focused. Audio decoding and Remote Play over Internet hole punching are disabled. `ffmpeg` is required only to turn captured H.264 frames into PNG files; `ffplay` is optional for live video.

Check the Python sources:

```bash
python3 -m py_compile chiaki_python/*.py examples/*.py
```

## Profiles

Profiles are read from `~/.config/Chiaki/Chiaki.conf`. List only nicknames and platform flags, not credentials:

```bash
python3 - <<'PY'
from chiaki_python.config_parser import parse_chiaki_config
for host in parse_chiaki_config():
    print(host.get('name'), 'PS5' if host.get('is_ps5') else 'PS4')
PY
```

Examples accept either a nickname or a registration JSON path. If the saved address is stale, override it for that invocation:

```bash
export CHIAKI_HOST=CONSOLE_IP
```

Do not print `regist_key`, `rp_key`, authentication logs, or the contents of registration JSON files.

## Screenshot-first control

Capture the current screen before navigating:

```bash
mkdir -p captures
CHIAKI_HOST=CONSOLE_IP python3 examples/screenshot.py PROFILE captures/home.png
```

`PROFILE` can be a nickname such as `1360` or a JSON path such as `captures/current-pair.json`. The screenshot example sends a short PS-button press to wake the display, requests a fresh keyframe, and decodes it with ffmpeg. Inspect the image before choosing the next action.

For live video on a machine with a display:

```bash
CHIAKI_HOST=CONSOLE_IP python3 examples/stream.py PROFILE
```

## Controller scripts

Create a small script under `captures/`, for example `captures/navigate.txt`:

```text
# Move one item right, wait, then select it
RIGHT 0.15
DELAY 0.5
CROSS 0.15
```

Run it:

```bash
CHIAKI_HOST=CONSOLE_IP python3 examples/controller_script.py captures/navigate.txt PROFILE
```

Supported buttons include `PS`, `CROSS`/`X`, `CIRCLE`/`O`, `SQUARE`, `TRIANGLE`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `L1`, `R1`, `L2`, `R2`, `L3`, `R3`, `OPTIONS`, `SHARE`, and `TOUCHPAD`. Button durations are seconds. `DELAY` also takes seconds.

The script runner opens `ffplay` for video. On a headless host, use the `PS4Controller` class from `examples/controller.py` in a short Python snippet instead; despite its name, it honors the profile's PS5 flag. Connect, use `press()`, `left_stick()`, `right_stick()`, or `triggers()`, then call `release_all()` and stop/destroy the session in `finally`.

Always capture another screenshot after navigation. Restore the previous selection when a test does not require a persistent change.

## Registering a new local profile

Use registration only if existing profiles are rejected or belong to a different console. On the PS5, open:

```text
Settings > System > Remote Play > Pair Device
```

Keep the PIN screen open, then run within its time limit:

```bash
python3 examples/register.py CONSOLE_IP PIN captures/current-pair.json \
  --account-id-hex ACCOUNT_ID_16_HEX_DIGITS
```

The account ID is exactly 8 bytes written as 16 hexadecimal digits. Use the account ID's normal display order, not the reversed bytes stored in an SFO. The default registration target is `CHIAKI_TARGET_PS5_1` (`1000100`). The output is a new JSON profile; do not print it.

Use that profile immediately:

```bash
CHIAKI_HOST=CONSOLE_IP python3 examples/screenshot.py \
  captures/current-pair.json captures/paired-home.png
```

Registration logging is disabled in this example. A failure does not create a usable profile. Verify the account ID, target, user permissions, and fresh PIN rather than repeatedly guessing credentials.

## Reboot and jailbreak recovery

1. Before rebooting, verify the power-menu selection with a screenshot and choose **Restart PS5**, not Rest Mode or Turn Off.
2. Wait for Remote Play to respond. Use `CHIAKI_HOST` if the console receives a new address.
3. Capture the home screen through Chiaki and launch the jailbreak app with small, screenshot-verified steps.
4. Only after the jailbreak services are running, reload payload tools such as the ELF loader, klog client, or PS5_DevLoop.
5. If the console is unreachable, do not assume a press landed. Check power, network discovery, and the current address before trying more input.

## Troubleshooting

- `403` during session control: the profile may belong to another console or the registration may be stale. Confirm hardware and user, then register a new local profile if needed.
- `No route to host`: the console is offline, waking, or has a new address. Do not keep sending controller scripts.
- No frame after connection: request a fresh screenshot, wait briefly for video, and confirm the console is not on a Remote Play blocked screen.
- Import/build errors: rerun `./build.sh` after initializing submodules, then run the Python compile check above.
