# Mobile App

This folder contains a native mobile client for the existing Yerevan site.

## What is included

- `Home` screen with the project story and visual context.
- `Yerevan` screen with native sliders and a real mobile map.
- `Compare` screen with native SVG rendering of business areas in a shared meters scale.
- `Theory` screen with native SVG charts based on the analytical model.

## Data source

Run the export script from the project root to refresh mobile assets from the current generated site:

```powershell
& 'C:\Users\Nedric\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\export_mobile_assets.py
```

The script writes JSON payloads into `src/data` and copies image assets into `assets/images`.

## Run

The project is configured for Expo SDK 55 and requires Node.js 20.19 or newer.

1. Install the dependencies for the Expo project:

```powershell
npm install
```

2. Start the app:

```powershell
npx expo start
```

3. Launch on Android:

```powershell
npx expo start --android
```

If you installed Node.js while this terminal was already open, close and reopen PowerShell once so the `node` and `npm` commands are available in `PATH`.
