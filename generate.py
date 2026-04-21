#!/usr/bin/env python3
"""Generate Sora 2 Pro videos from YAML prompt files."""

import argparse
import os
import time
from pathlib import Path

import yaml
from openai import OpenAI

OUTPUTS_DIR = Path("outputs")
PROMPTS_DIR = Path("prompts")

VALID_SIZES = {"720x1280", "1280x720", "1024x1792", "1792x1024"}
VALID_SECONDS = {4, 8, 12, 16, 20}


def load_prompt(path: Path) -> dict:
    with open(path) as f:
        data = yaml.safe_load(f)

    size = data.get("size", "1280x720")
    seconds = int(data.get("seconds", 8))

    if size not in VALID_SIZES:
        raise ValueError(f"Invalid size '{size}'. Choose from: {VALID_SIZES}")
    if seconds not in VALID_SECONDS:
        raise ValueError(f"Invalid seconds '{seconds}'. Choose from: {VALID_SECONDS}")

    return {
        "prompt": data["prompt"],
        "size": size,
        "seconds": seconds,
        "model": data.get("model", "sora-2-pro"),
    }


def generate_video(client: OpenAI, spec: dict, output_path: Path) -> None:
    print(f"  Submitting: {spec['model']} | {spec['size']} | {spec['seconds']}s")

    video = client.videos.create(
        model=spec["model"],
        prompt=spec["prompt"],
        size=spec["size"],
        seconds=spec["seconds"],
    )

    print(f"  Job ID: {video.id} — waiting for completion...")
    while video.status in ("queued", "in_progress"):
        time.sleep(5)
        video = client.videos.retrieve(video.id)
        print(f"  Status: {video.status}")

    if video.status != "completed":
        raise RuntimeError(f"Generation failed with status: {video.status}")

    content = client.videos.download_content(video.id, variant="video")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content.write_to_file(str(output_path))
    print(f"  Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate Sora 2 Pro videos from prompts.")
    parser.add_argument(
        "prompts",
        nargs="*",
        help="YAML prompt files to process (default: all files in prompts/)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip generation if output file already exists (default: true)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable not set.")

    client = OpenAI(api_key=api_key)

    prompt_files = (
        [Path(p) for p in args.prompts]
        if args.prompts
        else sorted(PROMPTS_DIR.glob("*.yaml"))
    )

    if not prompt_files:
        print("No prompt files found. Add YAML files to prompts/ or pass paths as arguments.")
        return

    for prompt_path in prompt_files:
        name = prompt_path.stem
        output_path = OUTPUTS_DIR / f"{name}.mp4"

        print(f"\n[{name}]")

        if args.skip_existing and output_path.exists():
            print(f"  Skipping — {output_path} already exists.")
            continue

        spec = load_prompt(prompt_path)
        generate_video(client, spec, output_path)

    print("\nDone.")


if __name__ == "__main__":
    main()
