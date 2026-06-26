from __future__ import annotations

import base64
import io
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Sequence

from PIL import Image, ImageDraw, ImageFont

from common import base_parser, repo_root, score_keyword_groups, timestamp, write_jsonl


def load_font(name: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def image_to_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_shape_card() -> str:
    image = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(image)
    font_big = load_font("arial.ttf", 42)
    font_small = load_font("arial.ttf", 30)

    draw.rectangle((40, 40, 600, 320), outline="black", width=6)
    draw.rectangle((70, 85, 250, 230), fill=(30, 120, 220))
    draw.ellipse((390, 90, 540, 240), fill=(220, 60, 60))
    draw.text((75, 260), "LABAGENT VL TEST 42", fill="black", font=font_big)
    draw.text((275, 135), "blue square + red circle", fill="black", font=font_small)
    return image_to_data_url(image)


def build_dashboard_card() -> str:
    image = Image.new("RGB", (900, 520), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    font_title = load_font("arial.ttf", 38)
    font = load_font("arial.ttf", 26)
    font_mono = load_font("consola.ttf", 24)

    draw.rectangle((20, 20, 880, 500), fill="white", outline=(60, 60, 60), width=3)
    draw.text((45, 45), "LabAgent Routing Dashboard", fill=(20, 20, 20), font=font_title)

    rows = [
        ("Model", "Node", "Status"),
        ("qwen-agent", "5090", "OK"),
        ("embed-local", "NewDevice", "OK"),
        ("vision-local", "NewDevice", "OK"),
        ("qwen-think", "5090", "PLANNED"),
    ]
    x_positions = [55, 330, 575]
    y0 = 125
    row_h = 58
    for index, row in enumerate(rows):
        y = y0 + index * row_h
        fill = (230, 238, 248) if index == 0 else (255, 255, 255)
        draw.rectangle((45, y, 840, y + row_h), fill=fill, outline=(180, 180, 180), width=2)
        for cell_index, text in enumerate(row):
            draw.text((x_positions[cell_index], y + 15), text, fill=(0, 0, 0), font=font_mono)
    draw.text((55, 445), "Alert: RAG tunnel :18010 manual, not systemd.", fill=(160, 40, 40), font=font)
    return image_to_data_url(image)


TASKS = [
    {
        "id": "shape_ocr",
        "prompt": (
            "Return compact JSON only. Describe the image. Include keys: text, shapes. "
            "The text value must contain any visible English words and numbers."
        ),
        "image_factory": build_shape_card,
        "expected_keyword_groups": [
            ["LABAGENT"],
            ["VL"],
            ["TEST"],
            ["42"],
            ["blue"],
            ["square"],
            ["red"],
            ["circle"],
        ],
    },
    {
        "id": "dashboard_ocr",
        "prompt": (
            "Return compact JSON only. Read the dashboard table rows and alert text. "
            "Do not explain. Include a rows array with exactly 4 objects, one for each non-header "
            "table row. Each row object must include model, node, and status. Also include alert."
        ),
        "image_factory": build_dashboard_card,
        "expected_keyword_groups": [
            ["qwen-agent"],
            ["5090"],
            ["embed-local"],
            ["vision-local"],
            ["qwen-think"],
            ["PLANNED"],
            ["18010"],
            ["manual"],
            ["systemd"],
        ],
    },
]


def normalize_for_score(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def call_vision(
    base_url: str,
    api_key: str | None,
    timeout: int,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    started = time.perf_counter()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        return {
            "ok": True,
            "latency_seconds": time.perf_counter() - started,
            "content": content,
            "finish_reason": choice.get("finish_reason"),
            "usage": data.get("usage") or {},
            "raw_model": data.get("model"),
        }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "latency_seconds": time.perf_counter() - started,
            "http_status": exc.code,
            "error": f"HTTPError: {exc}",
            "error_body": exc.read().decode("utf-8", errors="replace")[:2000],
        }
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "latency_seconds": time.perf_counter() - started,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = base_parser("Check vision-local image OCR and screenshot understanding.")
    parser.set_defaults(model="vision-local")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "benchmarks" / "results" / f"vision_local_{timestamp()}.jsonl",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=220,
        help="max_tokens for each vision request.",
    )
    args = parser.parse_args()

    results: List[Dict[str, Any]] = []
    failures = 0
    for task in TASKS:
        payload = {
            "model": args.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": task["prompt"]},
                        {"type": "image_url", "image_url": {"url": task["image_factory"]()}},
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": args.max_tokens,
        }
        response = call_vision(args.base_url, args.api_key, args.timeout, payload)
        content = normalize_for_score(response.get("content") or "")
        scoring = score_keyword_groups(content, task["expected_keyword_groups"])
        passed = bool(response.get("ok")) and scoring["keyword_group_passed"]
        if response.get("finish_reason") == "length":
            passed = False
        row: Dict[str, Any] = {
            "id": task["id"],
            "model": args.model,
            "passed": passed,
            "content": content,
            "content_len": len(content),
            **response,
            **scoring,
        }
        results.append(row)
        write_jsonl(args.output, results)
        status = "PASS" if passed else "FAIL"
        print(
            f"[{status}] {task['id']} "
            f"finish={response.get('finish_reason')} matched={len(scoring['matched_keyword_groups'])}/"
            f"{len(scoring['expected_keyword_groups'])}"
        )
        if not passed:
            failures += 1

    write_jsonl(args.output, results)
    print(f"Wrote {args.output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
