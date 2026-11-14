"""Run the packaged application checks, isolated from local credentials and data."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    node = shutil.which("node")
    if not node:
        print("Install Node.js (20 or later) to check the Gemini extension and n8n contract.")
        return 1
    folder = ROOT / "data" / "test-runs"
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verify-", dir=folder) as temp:
        env = dict(os.environ, PYTHONUTF8="1", PYTHON_DOTENV_DISABLED="1",
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", ENABLE_NGROK="0",
                   LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false",
                   ENABLE_TIKTOK_SANDBOX_SIMULATION="false", CONTENT_V2_ACCEPTANCE_MODE="0",
                   STUDIO_DATA_DIR=str(Path(temp) / "studio"), HANDOFF_DATA_DIR=str(Path(temp) / "automation"),
                   LONG_AUTOMATION_ROOT=str(ROOT / "integrations/long-v2"),
                   PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "integrations/long-v2/python-service")]))
        # Empty values also prevent older dotenv versions from loading real credentials.
        for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                    "NOTION_TOKEN", "NOTION_DATABASE_ID", "NOTION_V2_DATABASE_ID", "NOTION_TOKENS_DB_ID",
                    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_WEBHOOK_SECRET",
                    "TELEGRAM_AUTHORIZED_USER_IDS", "WEBHOOK_V2_TOKEN", "TIKTOK_CLIENT_KEY",
                    "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI", "NGROK_AUTH_TOKEN"):
            env[key] = ""
        commands = [
            ("Content Studio, contracts, packaged files and v1/v2", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-q"]),
            ("Automation regression checks", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "integrations/long-v2/tests/test_fixes.py"]),
            ("Gemini extension", [node, "--test", "tests/gemini_extension.test.mjs"]),
        ]
        for label, command in commands:
            print(f"Checking {label}...", flush=True)
            try:
                result = subprocess.run(command, cwd=ROOT, env=env, timeout=300,
                                        capture_output=True, text=True, encoding="utf-8", errors="replace")
            except (OSError, subprocess.TimeoutExpired) as exc:
                print(f"Check could not finish: {type(exc).__name__}", flush=True)
                return 1
            output = result.stdout + result.stderr
            if result.returncode:
                print(output)
                return result.returncode
            print("\n".join(output.strip().splitlines()[-10:]), flush=True)
        print("All checks passed. Live AI/video/Notion/Telegram/TikTok were not used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
