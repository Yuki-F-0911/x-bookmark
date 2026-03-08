#!/usr/bin/env python3
"""
フル自動パイプライン: 情報収集 → 要約 → ニュースレター生成 → 配信

毎日1コマンドで収益化コンテンツを生成する統合スクリプト。

使い方:
  python full_pipeline.py                    # フル実行（Slack通知 + 記事生成）
  python full_pipeline.py --newsletter-only  # 記事生成のみ（digest_cache.jsonから）
  python full_pipeline.py --dry-run          # テスト実行（Slack送信なし）
  python full_pipeline.py --format note      # Note向け記事を生成
"""

import sys
import io
import os
import json
import argparse
import requests
from datetime import datetime
from pathlib import Path
from subprocess import run as subprocess_run, PIPE
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
NEWSLETTER_DIR = PROJECT_ROOT / "newsletters"


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def run_step(name: str, cmd: list[str]) -> bool:
    log(f"▶ {name}")
    result = subprocess_run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=PROJECT_ROOT)
    if result.returncode != 0:
        log(f"✗ {name} 失敗: {result.stderr[:300]}", "ERROR")
        return False
    log(f"✓ {name} 完了")
    return True


def main():
    parser = argparse.ArgumentParser(description="フル自動パイプライン")
    parser.add_argument("--newsletter-only", action="store_true",
                        help="ニュースレター生成のみ（ダイジェスト処理をスキップ）")
    parser.add_argument("--dry-run", action="store_true",
                        help="Slack送信をスキップ")
    parser.add_argument("--format", choices=["plain", "note", "substack"],
                        default="plain", help="記事フォーマット")
    parser.add_argument("--no-ai-article", action="store_true",
                        help="記事生成にClaude APIを使わない（テンプレートのみ）")
    args = parser.parse_args()

    python = sys.executable
    today = datetime.now().strftime("%Y-%m-%d")
    log(f"=== フル自動パイプライン開始 ({today}) ===")

    # Step 1: ダイジェスト処理（ブックマーク収集→要約→Slack通知）
    if not args.newsletter_only:
        digest_cmd = [python, "-m", "src.main"]
        if args.dry_run:
            digest_cmd.append("--dry-run")
        digest_cmd.extend(["--skip-enrich"])  # 高速化のためエンリッチメントスキップ

        if not run_step("ブックマークダイジェスト処理", digest_cmd):
            log("ダイジェスト処理に失敗。ニュースレター生成をスキップします。", "WARN")
            sys.exit(1)

    # Step 2: ニュースレター記事生成
    NEWSLETTER_DIR.mkdir(exist_ok=True)
    output_file = f"{today}.md"

    newsletter_cmd = [
        python, str(SCRIPT_DIR / "generate_newsletter.py"),
        "--output", output_file,
        "--format", args.format,
    ]
    if args.no_ai_article:
        newsletter_cmd.append("--no-ai")

    if not run_step("ニュースレター記事生成", newsletter_cmd):
        log("記事生成に失敗しましたが、ダイジェストは完了しています。", "WARN")
        sys.exit(1)

    output_path = NEWSLETTER_DIR / output_file

    # Step 3: 成瀬テーマ抽出（オプション）
    naruse_cmd = [python, str(SCRIPT_DIR / "naruse" / "integrated_daily_pipeline.py")]
    run_step("成瀬テーマ抽出", naruse_cmd)  # 失敗しても続行

    # Step 4: 記事完成通知をSlackに送信
    if not args.dry_run and output_path.exists():
        notify_newsletter_ready(output_path)

    log(f"=== パイプライン完了 ===")
    log(f"📄 記事ファイル: {output_path}")


def notify_newsletter_ready(article_path: Path) -> None:
    """生成されたニュースレターの冒頭をSlackに通知"""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        log("SLACK_WEBHOOK_URL未設定のためニュースレター通知をスキップ", "WARN")
        return

    try:
        content = article_path.read_text(encoding="utf-8")
        # frontmatter除去
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        preview = content[:500] + ("..." if len(content) > 500 else "")

        payload = {
            "text": f"📝 *ニュースレター記事が生成されました*\n\n{preview}\n\n_ファイル: {article_path.name}_",
        }
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        log("Slackにニュースレター通知を送信しました")
    except Exception as e:
        log(f"Slack通知失敗: {e}", "WARN")


if __name__ == "__main__":
    main()
