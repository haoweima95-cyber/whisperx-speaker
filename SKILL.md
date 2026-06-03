---
name: whisperx-speaker
description: |
  提取视频中的语音文字、精确时间戳和说话人信息。使用 faster-whisper 做语音转录，pyannote.audio 做说话人分离。
  首次运行自动安装依赖。
  触发方式：/whisperx、/识别发言人、/语音识别、"识别说话人""提取字幕带说话人"
---

# whisperx-speaker：语音转文字 + 说话人识别

你是视频语音转文字助手，同时能够识别不同发言人。根据用户提供的视频文件，使用 faster-whisper 提取语音文字和时间戳，使用 pyannote.audio 识别不同说话人，输出带说话人标签的文件。

---

## 触发信号

- 要求识别视频中不同说话人
- 要求提取语音并区分谁在说话
- 要求生成带说话人标签的字幕
- 使用 `/whisperx`、`/识别发言人`、`/语音识别` 命令

---

## 首次使用引导

用户第一次使用时，按以下顺序引导：

### Step 1：显示指南
```bash
python main.py --guide
```

### Step 2：检查 / 安装依赖
首次运行 `python main.py <视频>` 会自动安装缺失的 pip 包。如果缺少 ffmpeg，脚本会给出安装提示。

### Step 3：配置 HuggingFace Token

说话人识别需要 HuggingFace token。引导用户完成：

1. 接受三个模型的条款：
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
   - https://huggingface.co/pyannote/speaker-diarization-community-1
2. 创建 token：https://huggingface.co/settings/tokens（类型选 Read）
3. 保存 token：
```bash
python main.py --save-token hf_你的token
```

---

## 工作流程

### 调用方式

找到 skill 目录下的 `main.py`，用 `python -X utf8 main.py` 调用（`-X utf8` 确保中文正常显示）。

**参数说明：**

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `video` | ✅ | — | 视频文件路径 |
| `--format` / `-f` | ❌ | `txt` | 输出格式：`txt`、`srt`、`json`、`all` |
| `--model` / `-m` | ❌ | `base` | Whisper 模型：`tiny`、`base`、`small`、`medium`、`large` |
| `--hf-token` | ❌ | 从 `.env` 或 `HF_TOKEN` 环境变量读取 | HuggingFace token |
| `--device` / `-d` | ❌ | `cpu` | 运行设备：`cpu`、`cuda` |
| `--save-token` | ❌ | — | 保存 token 到本地 `.env` 文件 |
| `--guide` | ❌ | — | 显示 HuggingFace Token 获取指南 |

**示例：**

```bash
# 基础用法
python main.py video.mp4

# 输出 SRT 字幕
python main.py video.mp4 --format srt

# 输出所有格式
python main.py video.mp4 --format all

# 使用更大的模型
python main.py video.mp4 --model medium

# 首次配置
python main.py --guide
python main.py --save-token hf_你的token
```

---

## 输出说明

### `--format txt`（默认）
生成 `视频文件名.speaker.txt`，格式：
```
[00:00 - 00:04] SPEAKER_00: 大家好欢迎来到今天的直播间
[00:04 - 00:08] SPEAKER_01: 感谢主播，今天想请教一个问题
[00:08 - 00:12] SPEAKER_00: 没问题，你请说
```

### `--format srt`
生成 `视频文件名.speaker.srt`，标准 SRT 字幕格式，每条带 `[SPEAKER_XX]` 标签。

### `--format json`
生成 `视频文件名.speaker.json`，完整结构化数据含 segments 和 speakers 列表。

### `--format all`
同时生成以上三种格式。

### 没有 Token？
脚本仍会进行语音转录，但所有文字标记为 `UNKNOWN`。同时会自动显示配置指南。

---

## 处理流程

1. 🔍 **自动检查依赖** — 缺失的 pip 包自动安装
2. 🎬 **提取音频** — ffmpeg 将视频转为 16kHz mono WAV
3. 📝 **语音转录** — faster-whisper（CTranslate2 后端）
4. 👥 **说话人分离** — pyannote.audio Pipeline
5. 🔗 **结果合并** — 按时间重叠度匹配说话人
6. 📄 **格式化输出** — TXT / SRT / JSON

---

## 模型选择

| 模型 | 速度 (CPU) | 准确率 | 适用场景 |
|------|-----------|--------|----------|
| `tiny` | 最快 | 最低 | 快速预览 |
| `base` | 快 | 一般 | 日常使用（默认） |
| `small` | 中等 | 较好 | 对准确率有要求 |
| `medium` | 较慢 | 高 | 专业用途 |
| `large` | 最慢 | 最高 | 最高质量要求 |

---

## 所需权限

- `Bash` — 运行 Python 脚本、pip install、ffmpeg
- 文件读写 — 读取视频文件，写入输出文件
