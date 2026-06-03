# WhisperX Speaker - 视频语音转文字 + 说话人识别

基于 **faster-whisper** + **pyannote.audio** 的 Claude Code Skill，从视频中提取语音文字、时间戳，并自动识别不同发言人。

## 效果预览

```
🎬 处理: meeting.mp4
🖥️ 设备: cpu
📝 正在进行语音转录...
  检测到语言: zh (概率: 1.00)
  共 58 个语音片段
👥 正在识别不同发言人...
🔗 正在匹配说话人与文字...
✅ TXT: meeting.speaker.txt

📊 共识别出 2 位发言人: SPEAKER_00, SPEAKER_01

📝 内容预览：
[00:00 - 00:10] SPEAKER_00: 大家好欢迎来到今天的直播间
[00:10 - 00:23] SPEAKER_01: 感谢主播，今天想请教一个问题
[00:23 - 00:34] SPEAKER_00: 没问题，你请说
```

## 安装

### 1. 克隆到 Claude Code skills 目录

```bash
# Windows
git clone https://github.com/你的用户名/whisperx-speaker.git %USERPROFILE%\.claude\skills\whisperx-speaker

# Mac / Linux  
git clone https://github.com/你的用户名/whisperx-speaker.git ~/.claude/skills/whisperx-speaker
```

### 2. 自动安装依赖

首次运行时，脚本会自动检测并安装缺失的 Python 包：

```bash
python main.py --guide
```

你也可以手动安装：

```bash
pip install faster-whisper pyannote.audio scipy
```

### 3. 配置 HuggingFace Token（必需，用于说话人识别）

说话人识别功能需要 HuggingFace token。按以下步骤配置：

**第 1 步：接受模型使用条款（共 3 个模型）**

| 模型 | 链接 |
|------|------|
| Speaker Diarization 3.1 | https://huggingface.co/pyannote/speaker-diarization-3.1 |
| Segmentation 3.0 | https://huggingface.co/pyannote/segmentation-3.0 |
| Speaker Diarization Community 1 | https://huggingface.co/pyannote/speaker-diarization-community-1 |

每个链接 → 点击 **"Agree and access repository"**

**第 2 步：创建 Access Token**

访问 https://huggingface.co/settings/tokens → 创建新 token → Token type 选 **Read**

**第 3 步：保存 Token（任选一种）**

```bash
# 方式 A（推荐）：保存到本地配置文件
python main.py --save-token hf_你的token

# 方式 B：设置环境变量
# Windows
setx HF_TOKEN "hf_你的token"
# Mac/Linux  
export HF_TOKEN=hf_你的token >> ~/.bashrc

# 方式 C：每次命令行传入
python main.py video.mp4 --hf-token hf_你的token
```

## 使用

### 基础用法

```bash
# 转录 + 识别说话人
python main.py video.mp4

# 输出 SRT 字幕
python main.py video.mp4 --format srt

# 输出所有格式（TXT + SRT + JSON）
python main.py video.mp4 --format all

# 使用更大的模型提高准确率
python main.py video.mp4 --model medium
```

### Claude Code 中使用

安装后在 Claude Code 中直接调用：

```
/whisperx D:\videos\meeting.mp4
/whisperx D:\videos\meeting.mp4 --format all --model medium
```

### 输出格式

| 格式 | 文件名 | 说明 |
|------|--------|------|
| `txt` | `视频名.speaker.txt` | `[时间戳] 发言人: 文字` |
| `srt` | `视频名.speaker.srt` | 标准字幕格式 + 发言人标签 |
| `json` | `视频名.speaker.json` | 完整结构化数据 |
| `all` | 以上全部 | 同时生成三种格式 |

## 模型选择

| 模型 | 速度 (CPU) | 准确率 | 适用场景 |
|------|-----------|--------|----------|
| `tiny` | 最快 | 最低 | 快速测试 |
| `base` | 快 | 一般 | 日常使用（默认） |
| `small` | 中等 | 较好 | 对准确率有要求 |
| `medium` | 较慢 | 高 | 专业用途 |
| `large` | 最慢 | 最高 | 最高质量要求 |

## 系统要求

- Python >= 3.8
- ffmpeg（用于提取视频音频）
  - Windows: `winget install Gyan.FFmpeg`
  - Mac: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- 首次运行会下载 Whisper 模型（约 1-10 GB，取决于模型大小）
- 首次运行会下载 pyannote 说话人分离模型（约 500 MB）

## 许可

MIT License

## 致谢

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - CTranslate2 后端的 Whisper 实现
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) - 说话人分离模型
