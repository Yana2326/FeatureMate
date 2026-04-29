"""
KB Agent — автоматическое создание статей базы знаний по фичам Altegio.

Использование:
    python agent.py --feature "Sell product" --path "Calendar → Sell product"
    python agent.py --feature "Sell product" --path "Calendar → Sell product" --description "Продажа товаров из карточки записи"
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import anyio
from dotenv import load_dotenv

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, SystemMessage, AssistantMessage, TextBlock
from prompts import SYSTEM_PROMPT, build_task
from export_pdf import export_pdf

load_dotenv()


def validate_env() -> tuple[str, str]:
    email = os.getenv("ALTEGIO_EMAIL")
    password = os.getenv("ALTEGIO_PASSWORD")
    if not email or not password:
        print("Error: ALTEGIO_EMAIL and ALTEGIO_PASSWORD must be set in .env")
        sys.exit(1)
    return email, password


def prepare_output_dir(feature_name: str) -> Path:
    folder_name = feature_name.lower().replace(" ", "_").replace("/", "_")
    output_dir = Path("output") / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def run_agent(feature_name: str, ui_path: str, description: str = "") -> None:
    email, password = validate_env()
    output_dir = prepare_output_dir(feature_name)

    print(f"\n{'='*60}")
    print(f"  KB Agent — Altegio Feature Documenter")
    print(f"{'='*60}")
    print(f"  Feature:     {feature_name}")
    print(f"  Path:        {ui_path}")
    if description:
        print(f"  Description: {description}")
    print(f"  Output:      {output_dir}/")
    print(f"{'='*60}\n")

    task = build_task(feature_name, ui_path, description)

    # Inject credentials into the task so the agent can log in
    task_with_creds = f"""{task}

## Credentials for login:
- Email: {email}
- Password: {password}
"""

    options = ClaudeAgentOptions(
        cwd=str(Path.cwd()),
        # The agent writes a fresh capture script (using altegio_helpers.py as
        # the foundation) and runs it via Bash. It also annotates PNGs and
        # generates the PDF, all of which need Bash + Glob + Grep + Edit.
        allowed_tools=["Write", "Read", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        system_prompt=SYSTEM_PROMPT,
        model="claude-opus-4-6",
        max_turns=60,
        mcp_servers={
            # Browser automation — navigate Altegio, take screenshots
            "playwright": {
                "command": "npx",
                "args": [
                    "@playwright/mcp@latest",
                    "--output-dir", str(output_dir.resolve()),
                    "--save-trace",
                ],
            },
            # NOTE: altegio-kb MCP disabled — its OAuth flow requires
            # interactive browser authorization which blocks autonomous runs.
            # The agent works fine without it (Playwright + the live UI is
            # the source of truth; KB articles are only a text reference).
        },
    )

    print("Starting agent...\n")

    try:
        async for message in query(prompt=task_with_creds, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print(f"\n{'='*60}")
                print("Agent finished.")
                print(f"Stop reason: {message.stop_reason}")
                print(f"{'='*60}")

                # ── PDF export ────────────────────────────────────────────
                article_md   = output_dir / "article.md"
                screenshots  = output_dir / "screenshots"
                article_pdf  = output_dir / "article.pdf"

                if article_md.exists():
                    print("\nExporting PDF…")
                    try:
                        export_pdf(article_md, screenshots, article_pdf)
                    except Exception as pdf_err:
                        print(f"  ⚠️  PDF export failed: {pdf_err}")
                else:
                    print("\n⚠️  article.md not found — skipping PDF export.")

                print(f"\nOutputs saved to: {output_dir}/")
                _list_outputs(output_dir)
            elif isinstance(message, SystemMessage):
                if message.subtype == "init":
                    session_id = message.data.get("session_id", "unknown")
                    print(f"Session ID: {session_id}\n")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        raise


def _list_outputs(output_dir: Path) -> None:
    files = list(output_dir.iterdir())
    if not files:
        print("No output files found.")
        return
    print("\nGenerated files:")
    for f in sorted(files):
        size = f.stat().st_size
        print(f"  {f.name:40s} {size:>8,} bytes")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="KB Agent — documents Altegio features automatically",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent.py --feature "Sell product" --path "Calendar → Sell product"
  python agent.py --feature "Online booking" --path "Settings → Online booking" --description "Настройка онлайн-записи клиентов"
        """,
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="Feature name (e.g. 'Sell product')",
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Navigation path in Altegio UI (e.g. 'Calendar → Sell product')",
    )
    parser.add_argument(
        "--description",
        default="",
        help="Optional brief description of the feature",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    anyio.run(run_agent, args.feature, args.path, args.description)


if __name__ == "__main__":
    main()
