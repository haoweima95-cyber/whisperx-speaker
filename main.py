#!/usr/bin/env python3
"""
Claude Code Skill: WhisperX 说话人识别 + 时间戳提取
=====================================================
使用 faster-whisper 做语音转录，pyannote.audio 做说话人分离。
首次运行会自动检查并安装缺失依赖。

用法:
  python main.py <视频文件> [--format txt/srt/json/all] [--model base] [--hf-token TOKEN]

环境变量:
  HF_TOKEN    HuggingFace token (用于说话人识别)
"""

import sys
import os
import json
import argparse
import tempfile
import subprocess
import shutil
from pathlib import Path

# Skill 目录 (用于读取 .env 等配置文件)
SKILL_DIR = Path(__file__).parent.resolve()


# ============================================================
# 首次运行引导
# ============================================================

def guide_hf_token():
    """打印 HuggingFace Token 获取完整指南"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║          🔑 说话人识别需要 HuggingFace Token                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  请按以下步骤操作（约 2 分钟）：                                ║
║                                                              ║
║  第 1 步：接受模型使用条款（共 3 个模型）                        ║
║    a) https://huggingface.co/pyannote/speaker-diarization-3.1 ║
║       → 点击 "Agree and access repository"                   ║
║    b) https://huggingface.co/pyannote/segmentation-3.0       ║
║       → 点击 "Agree and access repository"                   ║
║    c) https://huggingface.co/pyannote/speaker-diarization-community-1 ║
║       → 点击 "Agree and access repository"                   ║
║                                                              ║
║  第 2 步：创建 Access Token                                   ║
║    https://huggingface.co/settings/tokens                    ║
║    → 点击 "Create new token"                                 ║
║    → Token type 选 "Read" (权限最低，足够使用)                ║
║    → 复制生成的 token (格式: hf_xxxx...)                     ║
║                                                              ║
║  第 3 步：传入 Token（任选一种）                               ║
║    方式 A (推荐): 设置环境变量                                ║
║      Windows:  setx HF_TOKEN "hf_你的token"                  ║
║      Mac/Linux: echo 'export HF_TOKEN=hf_你的token' >> ~/.bashrc ║
║    方式 B: 每次命令行传入                                     ║
║      python main.py video.mp4 --hf-token hf_你的token        ║
║    方式 C: 保存到本地配置文件                                  ║
║      运行: python main.py --save-token hf_你的token           ║
║      (会保存到 skill 目录下的 .env 文件，不会被上传)           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def save_token_to_env(token):
    """将 token 保存到 skill 目录的 .env 文件"""
    env_file = SKILL_DIR / ".env"
    env_file.write_text(f"HF_TOKEN={token}\n")
    print(f"✅ Token 已保存到 {env_file} (此文件已在 .gitignore 中，不会被上传)")


def load_token_from_env_file():
    """从 skill 目录的 .env 文件读取 token"""
    env_file = SKILL_DIR / ".env"
    if env_file.exists():
        content = env_file.read_text().strip()
        for line in content.split("\n"):
            if line.startswith("HF_TOKEN="):
                return line.split("=", 1)[1]
    return None


# ============================================================
# 依赖安装
# ============================================================

REQUIRED_PIP_PACKAGES = {
    "faster_whisper": "faster-whisper",
    "pyannote.audio": "pyannote.audio",
    "scipy": "scipy",
    "pypinyin": "pypinyin",
}


def check_pip_package(import_name):
    """检查 Python 包是否已安装"""
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def auto_install_dependencies():
    """自动检查并安装缺失的 pip 依赖"""
    missing = []
    for import_name, pip_name in REQUIRED_PIP_PACKAGES.items():
        if not check_pip_package(import_name):
            missing.append(pip_name)

    if not missing:
        return True

    print(f"\n📦 检测到缺失依赖: {', '.join(missing)}")
    print("正在自动安装...\n")

    for pkg in missing:
        print(f"  pip install {pkg} ...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode != 0:
                print(f"  ❌ 安装 {pkg} 失败:\n{result.stderr[:300]}")
                return False
            print(f"  ✅ {pkg} 安装完成")
        except Exception as e:
            print(f"  ❌ 安装 {pkg} 异常: {e}")
            return False

    print("\n✅ 所有依赖安装完成\n")
    return True


def check_ffmpeg():
    """检查 ffmpeg 是否可用"""
    if shutil.which("ffmpeg"):
        return True

    print("""
❌ 未找到 ffmpeg

ffmpeg 用于从视频中提取音频，需要单独安装：

  Windows:
    winget install Gyan.FFmpeg
    或从 https://ffmpeg.org/download.html 下载

  Mac:
    brew install ffmpeg

  Linux:
    sudo apt install ffmpeg

安装后请重新运行此脚本。
""")
    return False


# ============================================================
# 格式化工具
# ============================================================

def format_time_txt(seconds):
    """TXT 格式：HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_time_srt(seconds):
    """SRT 格式：HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ============================================================
# 音频提取
# ============================================================

def extract_audio(video_path, output_dir=None):
    """用 ffmpeg 从视频中提取 16kHz mono WAV 音频"""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    if output_dir is None:
        output_dir = tempfile.gettempdir()

    wav_path = Path(output_dir) / f"_whisperx_{video_path.stem}.wav"
    print(f"🎬 提取音频: {video_path.name}")

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-ac", "1",
        "-ar", "16000",
        "-sample_fmt", "s16",
        "-y",
        str(wav_path)
    ]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 提取失败:\n{result.stderr[:500]}")
        if not wav_path.exists():
            raise RuntimeError("ffmpeg 执行完成但未生成 WAV 文件")
        return wav_path
    except FileNotFoundError:
        raise RuntimeError("ffmpeg 未找到，请确认 ffmpeg 已安装并在 PATH 中")


# ============================================================
# 语音转录（faster-whisper）
# ============================================================

def transcribe(audio_path, model_size="base", device="cpu"):
    """使用 faster-whisper 进行语音转录"""
    print("📝 正在进行语音转录...")

    from faster_whisper import WhisperModel

    compute_type = "int8" if device == "cpu" else "float16"

    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    try:
        raw_segments, info = model.transcribe(
            str(audio_path),
            beam_size=5,
            language="zh",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
    except Exception as e:
        raise RuntimeError(f"语音转录失败: {e}")

    print(f"  检测到语言: {info.language} (概率: {info.language_probability:.2f})")

    segments = []
    for seg in raw_segments:
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})

    print(f"  共 {len(segments)} 个语音片段")
    return segments


# ============================================================
# 上下文纠错（基于文件名关键词 + 拼音相似度）
# ============================================================

def extract_keywords_from_filename(video_path):
    """
    从视频文件名中提取有意义的中文关键词（>= 2 个汉字）
    用于后续的语音转写纠错
    """
    import re

    filename = Path(video_path).stem

    # 移除常见的噪音标记
    # 去掉括号及其内容、下划线、数字、英文、特殊符号
    cleaned = re.sub(r'[\(（\[【].*?[\)）\]】]', ' ', filename)  # 括号内容
    cleaned = re.sub(r'_[a-f0-9]{8,}', ' ', cleaned)            # 文件hash
    cleaned = re.sub(r'[a-zA-Z0-9]+', ' ', cleaned)              # 英文数字
    cleaned = re.sub(r'[#＃@＠\-\—\.\,\，\。\!\！\?\？]', ' ', cleaned)  # 标点
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # 提取连续中文片段
    keywords = []
    for phrase in re.findall(r'[一-鿿]{2,}', cleaned):
        phrase = phrase.strip()
        if len(phrase) >= 2:
            keywords.append(phrase)

    # 对长度 >= 4 的关键词，也拆出 2-3 字子串作为额外参考
    extra = []
    for kw in keywords:
        if len(kw) >= 4:
            for i in range(len(kw) - 3):
                extra.append(kw[i:i+4])
            for i in range(len(kw) - 2):
                extra.append(kw[i:i+3])
    keywords.extend(extra)

    # 去重，按长度降序（优先匹配长词）
    seen = set()
    result = []
    for kw in sorted(set(keywords), key=len, reverse=True):
        if kw not in seen:
            seen.add(kw)
            result.append(kw)

    return result


def get_pinyin(text):
    """获取中文文本的拼音（无声调），失败返回原文本"""
    try:
        from pypinyin import lazy_pinyin, Style
        return ''.join(lazy_pinyin(text, style=Style.NORMAL, errors='ignore'))
    except Exception:
        return text


def phonetic_correct(segments, video_path):
    """
    基于文件名关键词 + 拼音相似度进行上下文纠错

    逻辑：
    1. 从视频文件名提取关键词
    2. 如果某个关键词没有在转录结果中出现，但存在拼音相似的短语
       则将其替换为正确的关键词
    """
    keywords = extract_keywords_from_filename(video_path)
    if not keywords:
        return segments

    # 把所有转录文本拼接，方便跨片段搜索
    text_parts = [(seg["text"], i) for i, seg in enumerate(segments)]
    full_text = ''.join(t[0] for t in text_parts)

    corrections = {}  # (old_text, start_pos) -> new_text

    for keyword in keywords:
        if len(keyword) < 2:
            continue

        # 如果关键词已存在于转录中，跳过
        if keyword in full_text:
            continue

        kw_pinyin = get_pinyin(keyword)
        kw_len = len(keyword)

        # 在全文滑动窗口搜索拼音相似的短语
        best_match = None
        best_score = 0.0

        for i in range(len(full_text) - kw_len + 1):
            candidate = full_text[i:i + kw_len]
            # 跳过已包含关键词的情况
            if candidate == keyword:
                continue
            # 只检查全中文窗口
            if not all('一' <= c <= '鿿' for c in candidate):
                continue

            cand_pinyin = get_pinyin(candidate)

            # 计算拼音相似度
            score = _pinyin_similarity(kw_pinyin, cand_pinyin)

            # 需要拼音高度相似但字符不同（才可能是错误）
            if score >= 0.9 and score > best_score and candidate != keyword:
                # 只有当候选不是已存在的正确关键词时才替换
                if candidate not in keywords:
                    best_score = score
                    best_match = candidate

        if best_match:
            corrections[best_match] = keyword

    if not corrections:
        return segments

    # 应用纠错
    print(f"\n🔧 上下文纠错: {len(corrections)} 处")
    for wrong, correct in corrections.items():
        print(f"  「{wrong}」 → 「{correct}」")

    for seg in segments:
        text = seg["text"]
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        seg["text"] = text

    return segments


def _pinyin_similarity(py1, py2):
    """
    计算两个拼音字符串的相似度 (0.0 ~ 1.0)
    使用编辑距离归一化
    """
    if py1 == py2:
        return 1.0
    if not py1 or not py2:
        return 0.0

    # 编辑距离
    m, n = len(py1), len(py2)
    if m == 0 or n == 0:
        return 0.0

    # 优化：只计算一次 DP
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if py1[i-1] == py2[j-1] else 1
            curr[j] = min(curr[j-1] + 1, prev[j] + 1, prev[j-1] + cost)
        prev = curr

    dist = prev[n]
    max_len = max(m, n)
    return 1.0 - (dist / max_len)


# ============================================================
# 说话人分离（pyannote.audio）
# ============================================================

def diarize(audio_path, hf_token, device="cpu"):
    """使用 pyannote.audio 进行说话人分离"""
    print("👥 正在识别不同发言人...")

    if not hf_token:
        raise ValueError("需要 HuggingFace token")  # 调用方会处理

    import torch
    import numpy as np
    from scipy.io import wavfile
    from pyannote.audio import Pipeline

    # scipy 读取 WAV（绕过 torchcodec）
    sample_rate, waveform_np = wavfile.read(str(audio_path))
    if waveform_np.dtype == np.int16:
        waveform = torch.from_numpy(waveform_np.astype(np.float32) / 32768.0)
    elif waveform_np.dtype == np.int32:
        waveform = torch.from_numpy(waveform_np.astype(np.float32) / 2147483648.0)
    else:
        waveform = torch.from_numpy(waveform_np.astype(np.float32))
    waveform = waveform.unsqueeze(0)

    # 重采样到 16kHz
    if sample_rate != 16000:
        print(f"  重采样: {sample_rate}Hz -> 16000Hz")
        import torchaudio.transforms as T
        waveform = T.Resample(orig_freq=sample_rate, new_freq=16000)(waveform)
        sample_rate = 16000

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=hf_token,
    )

    if device != "cpu" and torch.cuda.is_available():
        pipeline = pipeline.to(torch.device(device))

    audio_input = {"waveform": waveform, "sample_rate": sample_rate}
    diarization = pipeline(audio_input)
    return diarization


def parse_diarization(diarization):
    """解析 pyannote diarization 结果（兼容 3.x 和 4.x）"""
    if hasattr(diarization, 'speaker_diarization'):
        annotation = diarization.speaker_diarization  # pyannote 4.x
    else:
        annotation = diarization  # pyannote 3.x

    segments = []
    for speech_turn, _, speaker in annotation.itertracks(yield_label=True):
        segments.append({
            "start": speech_turn.start,
            "end": speech_turn.end,
            "speaker": speaker,
        })
    return segments


# ============================================================
# 结果合并
# ============================================================

def merge_segments(transcript_segments, diarization):
    """将转录片段与说话人标签按时间重叠度合并"""
    print("🔗 正在匹配说话人与文字...")
    diar_segments = parse_diarization(diarization)

    if not diar_segments:
        print("  ⚠️ 未检测到说话人信息")
        return [(s["start"], s["end"], "SPEAKER_00", s["text"]) for s in transcript_segments]

    merged = []
    for seg in transcript_segments:
        seg_start, seg_end = seg["start"], seg["end"]
        best_speaker, best_overlap = None, 0.0

        for ds in diar_segments:
            overlap = max(0.0, min(seg_end, ds["end"]) - max(seg_start, ds["start"]))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = ds["speaker"]

        if best_speaker is None:
            best_speaker = diar_segments[0]["speaker"]

        merged.append((seg_start, seg_end, best_speaker, seg["text"]))

    return merged


# ============================================================
# 输出格式化
# ============================================================

def save_txt(merged_segments, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for start, end, speaker, text in merged_segments:
            f.write(f"[{format_time_txt(start)} - {format_time_txt(end)}] {speaker}: {text}\n")
    return output_path


def save_srt(merged_segments, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, (start, end, speaker, text) in enumerate(merged_segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time_srt(start)} --> {format_time_srt(end)}\n")
            f.write(f"[{speaker}] {text}\n\n")
    return output_path


def save_json_output(merged_segments, output_path):
    data = {
        "segments": [
            {"start": s, "end": e, "speaker": sp, "text": t}
            for s, e, sp, t in merged_segments
        ],
        "speakers": list(set(sp for _, _, sp, _ in merged_segments)),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path


# ============================================================
# 主处理流程
# ============================================================

def process_video(video_path, output_format="txt", model_size="base", device="cpu", hf_token=None, correct_errors=True):
    """处理视频：提取音频 -> 转录 -> 说话人分离 -> 合并 -> 输出"""

    # 1. 自动安装依赖
    if not auto_install_dependencies():
        return None

    # 2. 检查 ffmpeg
    if not check_ffmpeg():
        return None

    # 3. 获取 HF token (优先级: 命令行 > .env 文件 > 环境变量)
    if hf_token is None:
        hf_token = load_token_from_env_file()
    if hf_token is None:
        hf_token = os.environ.get("HF_TOKEN", "")

    # 4. 检查 CUDA
    if device == "cuda":
        import torch
        if not torch.cuda.is_available():
            print("⚠️ CUDA 不可用，回退到 CPU")
            device = "cpu"

    print(f"🎬 处理: {Path(video_path).name}")
    print(f"🖥️ 设备: {device}")

    # 5. 提取音频
    try:
        wav_path = extract_audio(video_path)
    except Exception as e:
        print(f"❌ 音频提取失败: {e}")
        return None

    # 6. 语音转录
    try:
        segments = transcribe(wav_path, model_size, device)
    except Exception as e:
        print(f"❌ 语音转录失败: {e}")
        cleanup_temp(wav_path)
        return None

    if not segments:
        print("❌ 未检测到语音内容")
        cleanup_temp(wav_path)
        return None

    # 6b. 上下文纠错（基于文件名关键词）
    if correct_errors:
        segments = phonetic_correct(segments, video_path)

    # 7. 说话人分离
    if hf_token:
        try:
            diarization = diarize(wav_path, hf_token, device)
            merged = merge_segments(segments, diarization)
        except Exception as e:
            print(f"⚠️ 说话人分离失败: {e}")
            merged = [(s["start"], s["end"], "UNKNOWN", s["text"]) for s in segments]
    else:
        print("\n⚠️ 未提供 HuggingFace token，跳过说话人识别")
        guide_hf_token()
        merged = [(s["start"], s["end"], "UNKNOWN", s["text"]) for s in segments]

    # 8. 清理临时文件
    cleanup_temp(wav_path)

    # 9. 输出文件
    video_path = Path(video_path)
    output_files = []
    speakers = set(s for _, _, s, _ in merged)

    if output_format in ["txt", "all"]:
        f = save_txt(merged, video_path.with_suffix(".speaker.txt"))
        print(f"✅ TXT: {f}")
        output_files.append(str(f))

    if output_format in ["srt", "all"]:
        f = save_srt(merged, video_path.with_suffix(".speaker.srt"))
        print(f"✅ SRT: {f}")
        output_files.append(str(f))

    if output_format in ["json", "all"]:
        f = save_json_output(merged, video_path.with_suffix(".speaker.json"))
        print(f"✅ JSON: {f}")
        output_files.append(str(f))

    # 10. 摘要
    print(f"\n📊 共识别出 {len(speakers)} 位发言人: {', '.join(sorted(speakers))}")

    # 11. 预览
    if merged:
        print("\n📝 内容预览：")
        print("-" * 50)
        for start, end, speaker, text in merged[:8]:
            print(f"[{format_time_txt(start)} - {format_time_txt(end)}] {speaker}: {text}")
        if len(merged) > 8:
            print(f"... (共 {len(merged)} 段)")
        print("-" * 50)

    return output_files


def cleanup_temp(wav_path):
    try:
        if wav_path and wav_path.exists():
            wav_path.unlink()
    except Exception:
        pass


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="提取视频中的语音文字、时间戳和说话人信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py video.mp4
  python main.py video.mp4 --format srt
  python main.py video.mp4 --format all --model medium
  python main.py video.mp4 --hf-token hf_xxxxxxxxxxxx
  python main.py video.mp4 --device cuda --model large

首次使用:
  1. 运行: python main.py --save-token hf_你的token  (保存token到本地)
  2. 然后直接: python main.py video.mp4

环境变量:
  HF_TOKEN    HuggingFace token (用于说话人识别)
        """
    )
    parser.add_argument("video", nargs="?", help="视频文件路径")
    parser.add_argument("--format", "-f", default="txt", choices=["txt", "srt", "json", "all"],
                        help="输出格式（默认: txt）")
    parser.add_argument("--model", "-m", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 模型大小（默认: base）")
    parser.add_argument("--device", "-d", default="cpu", choices=["cpu", "cuda"],
                        help="运行设备（默认: cpu）")
    parser.add_argument("--hf-token", default=None,
                        help="HuggingFace token（用于说话人分离）")
    parser.add_argument("--save-token", default=None,
                        help="保存 token 到本地 .env 文件")
    parser.add_argument("--guide", action="store_true",
                        help="显示 HuggingFace Token 获取指南")
    parser.add_argument("--no-correct", action="store_true",
                        help="禁用基于文件名关键词的上下文纠错")

    args = parser.parse_args()

    # 特殊命令
    if args.guide:
        guide_hf_token()
        return 0

    if args.save_token:
        save_token_to_env(args.save_token)
        return 0

    # 检查是否有视频文件
    if not args.video:
        parser.print_help()
        print("\n💡 提示：首次使用请运行 python main.py --guide 查看配置指南")
        return 1

    result = process_video(
        video_path=args.video,
        output_format=args.format,
        model_size=args.model,
        device=args.device,
        hf_token=args.hf_token,
        correct_errors=not args.no_correct,
    )

    if result:
        print(f"\n✨ 完成！共生成 {len(result)} 个文件")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
