"""Record a manual Free-tier check for a specific Gemini key and chat model."""
import argparse
import hashlib
from pathlib import Path
from dotenv import dotenv_values, set_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=Path(__file__).resolve().parents[1] / '.env')
    parser.add_argument('--model', required=True)
    parser.add_argument('--confirm-free-tier', action='store_true', help='Only after checking this key/project and model in AI Studio.')
    args = parser.parse_args()
    if not args.confirm_free_tier:
        parser.error('Check the project Free tier and model quota in AI Studio first; then use --confirm-free-tier.')
    values = dotenv_values(args.env_file)
    key = (values.get('GEMINI_API_KEY') or '').strip()
    model = args.model.strip()
    if not key or not model or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._' for c in model):
        parser.error('Missing GEMINI_API_KEY in the selected .env or invalid model name.')
    fingerprint = hashlib.sha256((key + '\0' + model).encode()).hexdigest()
    for name, value in {'CHAT_MODEL': model, 'CHAT_FREE_TIER_FINGERPRINT': fingerprint,
                        'CHAT_AI_ENABLED': '1', 'CHAT_DAILY_LIMIT': values.get('CHAT_DAILY_LIMIT') or '20'}.items():
        set_key(str(args.env_file), name, value, quote_mode='always')
    print('Recorded the manual Free-tier check. Restart Content Studio to enable Gemini chat.')
    print('This records your check; it does not query billing or enable any Google paid service.')


if __name__ == '__main__':
    main()
