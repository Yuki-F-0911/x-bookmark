#!/usr/bin/env python3
"""
音声→記事変換 受託ワークフロー

クライアントから受け取った音声ファイルを処理し、note記事を納品するまでの
一連のフローを自動化するスクリプト。

使い方:
  python workflow.py input.vtt                          # VTTから記事生成
  python workflow.py input.mp3 --transcribe              # 音声→文字起こし→記事
  python workflow.py input.vtt --speakers "成瀬,坂本"    # 話者指定
  python workflow.py input.vtt --style formal            # フォーマル文体
"""

import sys
import io
import os
import re
import json
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 相槌・フィラーの辞書
FILLER_WORDS = {
    'はい', 'ええ', 'うん', 'あ', 'ああ', 'なるほど', 'そうですね', 'そうだね',
    'まあ', 'なんか', 'あの', 'えっと', 'んー', 'うーん', 'そっか', 'ほう',
    'へえ', 'ふむ', 'おお', 'わかりました', '了解', 'オッケー',
    'よろしくお願いします', 'お疲れ様です', 'ありがとうございます',
    'すみません', 'けど', 'けどね', 'で', 'なん',
}

OUTPUT_DIR = Path(__file__).parent / "deliverables"


def parse_vtt(filepath: Path) -> list[dict]:
    """VTTファイルをパースして発言リストを返す"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\n(.+?):(.*?)(?=\n\n|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)

    utterances = []
    for start_time, end_time, speaker, text in matches:
        utterances.append({
            'speaker': speaker.strip(),
            'text': text.strip(),
            'start': start_time,
            'end': end_time,
        })
    return utterances


def is_filler(text: str) -> bool:
    """相槌・フィラー判定"""
    cleaned = re.sub(r'[。、？?！!]', '', text.strip())
    if len(cleaned) < 5:
        return True
    if cleaned in FILLER_WORDS:
        return True
    return False


def extract_speakers(utterances: list[dict], target_speakers: list[str] | None = None) -> dict[str, list[str]]:
    """話者ごとの有意味発言を抽出"""
    speakers: dict[str, list[str]] = defaultdict(list)

    for utt in utterances:
        if is_filler(utt['text']):
            continue
        speaker = utt['speaker']
        if target_speakers and speaker not in target_speakers:
            continue
        speakers[speaker].append(utt['text'])

    return dict(speakers)


def merge_consecutive(texts: list[str], max_block_chars: int = 300) -> list[str]:
    """連続する短い発言をブロックにまとめる"""
    blocks = []
    current = []
    current_len = 0

    for text in texts:
        current.append(text)
        current_len += len(text)
        if current_len >= max_block_chars:
            blocks.append(''.join(current))
            current = []
            current_len = 0

    if current:
        combined = ''.join(current)
        if len(combined) > 30:
            blocks.append(combined)

    return blocks


def generate_article(speaker: str, blocks: list[str], style: str = "casual") -> str:
    """話者の記事を生成"""
    today = datetime.now().strftime("%Y-%m-%d")

    if style == "formal":
        intro = f"本稿では、{speaker}氏の主張を整理し、その要点をお伝えします。"
    else:
        intro = f"*{speaker}さんの核心的な発言をまとめています。*"

    lines = [
        f"# {speaker}さんが語ったこと",
        "",
        intro,
        "",
        "---",
        "",
    ]

    for idx, block in enumerate(blocks, 1):
        # 段落分け
        paragraphs = re.split(r'(。\s*)(で、|そして|それで|だから|ただ|でも|しかし|例えば|なので|また)', block)
        reconstructed = []
        current = ""
        for part in paragraphs:
            current += part
            if len(current) > 150 and current.endswith('。'):
                reconstructed.append(current.strip())
                current = ""
        if current.strip():
            reconstructed.append(current.strip())

        lines.append(f"## ポイント {idx}")
        lines.append("")
        for para in reconstructed:
            lines.append(para)
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"\n*作成日: {today}*")
    return "\n".join(lines)


def transcribe_audio(audio_path: Path) -> Path:
    """音声ファイルを文字起こし（Whisper使用）"""
    try:
        import whisper
    except ImportError:
        print("[ERROR] openai-whisperがインストールされていません", file=sys.stderr)
        print("  pip install openai-whisper", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] 文字起こし中: {audio_path.name}", file=sys.stderr)
    model = whisper.load_model("base")
    result = model.transcribe(str(audio_path), language="ja")

    # VTT形式で保存
    vtt_path = audio_path.with_suffix('.vtt')
    with open(vtt_path, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        for segment in result['segments']:
            start = _format_time(segment['start'])
            end = _format_time(segment['end'])
            text = segment['text'].strip()
            f.write(f"{start} --> {end}\n")
            f.write(f"Speaker: {text}\n\n")

    print(f"[OK] 文字起こし完了: {vtt_path}", file=sys.stderr)
    return vtt_path


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def main():
    parser = argparse.ArgumentParser(description="音声→記事変換ワークフロー")
    parser.add_argument("input", help="入力ファイル（VTT/SRT/音声）")
    parser.add_argument("--transcribe", action="store_true",
                        help="音声ファイルを先に文字起こしする")
    parser.add_argument("--speakers", help="対象話者をカンマ区切りで指定")
    parser.add_argument("--style", choices=["casual", "formal"], default="casual",
                        help="文体スタイル")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR),
                        help="出力ディレクトリ")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)

    # 音声ファイルの場合は文字起こし
    if args.transcribe or input_path.suffix.lower() in ('.mp3', '.m4a', '.wav', '.ogg', '.mp4'):
        input_path = transcribe_audio(input_path)

    # VTTパース
    utterances = parse_vtt(input_path)
    if not utterances:
        print("[ERROR] 発言が検出されませんでした", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] {len(utterances)}件の発言を検出", file=sys.stderr)

    # 話者フィルタ
    target_speakers = None
    if args.speakers:
        target_speakers = [s.strip() for s in args.speakers.split(',')]

    speakers_data = extract_speakers(utterances, target_speakers)
    print(f"[INFO] 主要話者: {', '.join(speakers_data.keys())}", file=sys.stderr)

    # 出力ディレクトリ
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 各話者の記事生成
    generated = []
    for speaker, texts in speakers_data.items():
        if len(texts) < 3:
            print(f"[SKIP] {speaker}: 有意味発言が少なすぎます（{len(texts)}件）", file=sys.stderr)
            continue

        blocks = merge_consecutive(texts)
        article = generate_article(speaker, blocks, args.style)

        safe_name = re.sub(r'[^\w]', '_', speaker)
        today = datetime.now().strftime("%Y%m%d")
        filename = f"{today}_{safe_name}.md"
        filepath = out_dir / filename

        filepath.write_text(article, encoding='utf-8')
        generated.append(filepath)
        print(f"[OK] {filename} ({len(article)}字)", file=sys.stderr)

    if generated:
        print(f"\n[完了] {len(generated)}件の記事を生成しました", file=sys.stderr)
        for f in generated:
            print(f"  → {f}", file=sys.stderr)
    else:
        print("[WARN] 記事を生成できませんでした", file=sys.stderr)


if __name__ == "__main__":
    main()
