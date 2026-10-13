import argparse
import os
from pathlib import Path
from .core import export_manifest, init_db, ingest

def main():
    parser = argparse.ArgumentParser(description="BeninSpeechLab Fon audio pipeline")
    parser.add_argument("command", choices=["init", "ingest", "export"])
    parser.add_argument("--data", default=os.environ.get("BENINSPEECH_DATA", "./data"))
    parser.add_argument("--file", type=Path)
    parser.add_argument("--speaker-id")
    parser.add_argument("--consent", action="store_true")
    parser.add_argument("--transcript")
    parser.add_argument("--output", type=Path, default=Path("exports/manifest.jsonl"))
    args = parser.parse_args()
    root = Path(args.data)
    if args.command == "init":
        init_db(root).close()
        print(f"Initialized {root}")
    elif args.command == "ingest":
        if not args.file or not args.speaker_id:
            parser.error("ingest requires --file and --speaker-id")
        print(ingest(root, args.file.read_bytes(), args.speaker_id, args.consent,
                     transcript=args.transcript))
    else:
        print(f"Exported {export_manifest(root, args.output)} reviewed recordings to {args.output}")

if __name__ == "__main__":
    main()
