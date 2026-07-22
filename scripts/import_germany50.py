import argparse
import hashlib
import json
from pathlib import Path

from topology_utils import import_sndlib_native


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-native", type=Path, required=True)
    parser.add_argument("--output-scenario", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--license-name", required=True)
    parser.add_argument("--license-url", required=True)
    parser.add_argument("--topology-name", default="sndlib-germany50")
    return parser.parse_args()


def main():
    args = parse_args()
    scenario = import_sndlib_native(
        args.source_native,
        topology_name=args.topology_name,
        source_url=args.source_url,
        license_name=args.license_name,
        license_url=args.license_url,
    )
    source_sha256 = sha256_file(args.source_native)
    metadata = {
        "source_file": str(args.source_native),
        "source_url": args.source_url,
        "source_sha256": source_sha256,
        "license_name": args.license_name,
        "license_url": args.license_url,
        "node_count": len(scenario["nodes"]),
        "link_count": len(scenario["links"]),
        "source_metadata": scenario.get("source_metadata", {}),
    }

    args.output_scenario.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.output_scenario.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
    args.metadata_output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scenario": str(args.output_scenario), "metadata": str(args.metadata_output)}, indent=2))


if __name__ == "__main__":
    main()
