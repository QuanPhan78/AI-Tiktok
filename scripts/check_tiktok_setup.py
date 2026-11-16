"""Read only a specified local .env; report setup without exposing any values."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integrations/long-v2/python-service'))
from dotenv import dotenv_values
from app.publishing_setup import configuration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / 'integrations/long-v2/.env')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if not args.env_file.is_file():
        print('Chưa tìm thấy file cấu hình được chỉ định.')
        return 1
    # Do not interpolate inherited secrets or write the environment/configuration.
    env = {k: v or '' for k, v in dotenv_values(args.env_file, interpolate=False).items()}
    report = configuration(env)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
