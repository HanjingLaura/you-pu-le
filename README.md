# 有谱了

纯钢琴演奏视频（或音频）→ MIDI → 网页上的大谱表草稿。

## 第一版做什么

- 上传 mp4 / mov / wav / mp3，最长 3 分钟
- 用 ffmpeg 抽单声道 16kHz 音频
- 用 ByteDance High-resolution Piano Transcription 转 MIDI
- 用 music21 量化并拆成高音 / 低音谱号
- 浏览器里用 OpenSheetMusicDisplay 看谱，下载 MIDI 和 MusicXML

这是草稿谱，不是出版谱。装饰音、踏板、临时变音、左右手交叉都可能要再改。

## 环境

- Windows，Python 3.10（仓库里的 `.venv` 按 3.10 建）
- Node 18+
- NVIDIA GPU 可选。当前默认会装 CPU 版 PyTorch（本机 Clash `127.0.0.1:7890` 没开时，2.5GB 的 CUDA 轮子下不动）。要 GPU：先开代理，再在 `backend` 里装 `torch` 的 cu124 轮子。

## 启动

第一次会下载约 165MB 的钢琴模型到用户目录 `piano_transcription_inference_data`。

```powershell
cd C:\Users\hj120\Desktop\Keyprint
.\start.ps1
```

或开两个终端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm run dev
```

浏览器打开 http://localhost:3000

## 目录

- `frontend`：Next.js 上传、进度、看谱
- `backend`：FastAPI + 转录 + 排谱
- `DESIGN.md`：界面约定
