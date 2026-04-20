from __future__ import annotations

import base64
import gzip
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
MOBILE_DIR = ROOT / "mobile_app"
MOBILE_DATA_DIR = MOBILE_DIR / "src" / "data"
MOBILE_ASSETS_DIR = MOBILE_DIR / "assets" / "images"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _balanced_json_after_marker(text: str, marker: str) -> dict:
    start = text.find(marker)
    if start == -1:
        raise RuntimeError(f"Could not find marker: {marker}")

    brace_start = text.find("{", start)
    if brace_start == -1:
        raise RuntimeError(f"Could not find JSON object after marker: {marker}")

    depth = 0
    in_string = False
    escaped = False
    end = None

    for idx in range(brace_start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break

    if end is None:
        raise RuntimeError(f"Could not parse balanced JSON after marker: {marker}")

    return json.loads(text[brace_start:end])


def _extract_precomputed_payload(path: Path) -> dict:
    html = _read_text(path)
    match = re.search(r'PAYLOAD_GZ_B64\s*=\s*"([^"]+)"', html)
    if not match:
        raise RuntimeError(f"Could not find PAYLOAD_GZ_B64 in {path}")

    compressed = base64.b64decode(match.group(1))
    return json.loads(gzip.decompress(compressed).decode("utf-8"))


def _extract_city_payload(path: Path) -> dict:
    html = _read_text(path)
    return _balanced_json_after_marker(html, "const cityPayload = ")


def _extract_boundary_payload(path: Path) -> dict:
    html = _read_text(path)
    data = _balanced_json_after_marker(html, "const data = ")
    boundary = data.get("city_boundary")
    if not boundary:
        raise RuntimeError("Could not find city_boundary in interactive model payload")
    return boundary


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _round_nested(value, digits: int):
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, list):
        return [_round_nested(item, digits) for item in value]
    if isinstance(value, dict):
        return {key: _round_nested(item, digits) for key, item in value.items()}
    return value


def _prepare_precomputed_for_mobile(payload: dict) -> dict:
    precomp: dict[str, dict] = {}

    for key, entry in payload["precomp"].items():
        precomp[key] = {
            "mu": {
                "lon": round(entry["mu"]["lon"], 6),
                "lat": round(entry["mu"]["lat"], 6),
            },
            "sep_m": round(entry["sep_m"], 1),
            "area_km2": round(entry["area_km2"], 2),
            "poly_geom": _round_nested(entry["poly_geom"], 6) if entry.get("poly_geom") else None,
        }

    return {
        "t_grid": {
            "min": round(payload["t_grid"]["min"], 2),
            "max": round(payload["t_grid"]["max"], 2),
            "step": round(payload["t_grid"]["step"], 2),
        },
        "a_grid": {
            "min": round(payload["a_grid"]["min"], 2),
            "max": round(payload["a_grid"]["max"], 2),
            "step": round(payload["a_grid"]["step"], 2),
        },
        "g": {
            "lon": round(payload["g"]["lon"], 6),
            "lat": round(payload["g"]["lat"], 6),
        },
        "precomp": precomp,
    }


def _prepare_city_payload_for_mobile(payload: dict) -> dict:
    cities = {}
    for city_name, city in payload["cities"].items():
        cities[city_name] = {
            "geom_m": _round_nested(city["geom_m"], 1),
            "area_km2": round(city["area_km2"], 2),
        }

    return {
        "extent_m": round(payload["extent_m"], 1),
        "cities": cities,
    }


def _prepare_boundary_for_mobile(payload: dict) -> dict:
    return _round_nested(payload, 6)


def _copy_asset(src_name: str, dst_name: str | None = None) -> None:
    src = DOCS_DIR / "assets" / src_name
    if not src.exists():
        raise FileNotFoundError(src)

    MOBILE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, MOBILE_ASSETS_DIR / (dst_name or src_name))


def main() -> None:
    precomputed = _extract_precomputed_payload(DOCS_DIR / "yerevan_precomputed_model.html")
    city_payload = _extract_city_payload(DOCS_DIR / "city_business_area_comparison.html")
    boundary = _extract_boundary_payload(DOCS_DIR / "yerevan_interactive_model.html")

    _write_json(
        MOBILE_DATA_DIR / "yerevan-precomputed.json",
        _prepare_precomputed_for_mobile(precomputed),
    )
    _write_json(
        MOBILE_DATA_DIR / "city-comparison.json",
        _prepare_city_payload_for_mobile(city_payload),
    )
    _write_json(
        MOBILE_DATA_DIR / "yerevan-boundary.json",
        _prepare_boundary_for_mobile(boundary),
    )

    _copy_asset("hero_cover.png")
    _copy_asset("city_centers_map.png")
    _copy_asset("historical_center_icon.png")
    _copy_asset("business_area_icon.png")
    _copy_asset("administrative_center_icon.png")

    print("Exported mobile data and image assets.")


if __name__ == "__main__":
    main()
