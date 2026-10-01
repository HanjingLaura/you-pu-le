# 有谱了

纯钢琴演奏视频（或音频）→ MIDI → 网页上的大谱表草稿。

四个界面：

- 校音：本机麦克风，实时音高
- 节拍：本机发声的节拍器
- 扒谱：钢琴独奏视频 / 音频 → MIDI → 大谱表草稿
- 移调：上传 MusicXML / MIDI，选原调和目标调，导出移调后的谱

扒谱仍是草稿谱，不是出版谱。装饰音、踏板、临时变音、左右手交叉都可能要再改。

## 转谱与移调算法

识音与节奏对齐分开处理。钢琴仍使用 [Piano Transcription Inference](https://github.com/qiuqiangkong/piano_transcription_inference)，单旋律使用 [librosa pYIN](https://librosa.org/doc/0.10.2/generated/librosa.pyin.html)。单旋律现在会短暂桥接丢失的音高帧、回溯音高切换的起点，并按重新起音切分同音重复。

- 上传 MIDI：按原有速度表把秒转换成拍数，包含中途变速，避免把八分音符的间隔当作一拍。
- 上传音频：使用 [librosa 动态规划节拍跟踪](https://librosa.org/doc/0.10.2/generated/librosa.beat.beat_track.html)，比较半速、原速和倍速候选；按局部节拍插值对齐音符起止时间。失败时退回合并和弦起音后的音符节奏估计。
- 单声部量化支持十六分音符和附点八分音符，不再统一压到八分音符。乐谱目前仍默认 4/4，不自动判断拍号；三连音、自由速度、弱起小节和复杂多声部仍需人工校对。
- `POST /jobs` 可附加表单参数 `bpm`（30–240）作为速度提示，界面暂未提供这个输入。节拍的半速／倍速有时无法仅凭声音唯一确定；已知速度可以帮助消除歧义。
- 调性移调默认选择最近音程（范围 −5 到 +6 半音，如 C→G 为下降五个半音）。乐器的记谱移调仍按乐器定义处理。MusicXML 和压缩 MXL 在本机和 Vercel 使用同一个 music21 引擎，保留多谱表、声部、连音、拍号与速度；MIDI 导出直接改事件音高，保留时间、踏板、控制事件和鼓轨，越界报错而不夹到边界音高。

没有用真实录音数据集验证识音准确率提升。回归验证包括已知旋律的合成音频、节拍脉冲、速度变化、快速同音重复和移调结构保留。Spotify 的 [Basic Pitch](https://github.com/spotify/basic-pitch) 和 [Beat This!](https://github.com/CPJKU/beat_this) 可作为后续真实录音对比候选；当前没有引入额外模型或替换钢琴模型。

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
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```powershell
cd frontend
npm run dev
```

浏览器打开 http://localhost:3000（页面会同源转发 `/jobs`、`/instruments` 到后端，不必再单独开 8000）。

Cloud Agent 上打开：点 Agents 窗口的插头图标 → Forwarded Ports → `localhost:3000`。手机上看这个对话时，本机地址打不到这台机器，请用电脑打开同一条 Agent，或在自己的 Windows 上跑 `.\start.ps1`。

## 目录

- `frontend`：Next.js，四个界面
- `backend`：FastAPI + 转录 + 排谱 + 乐器移调
- `DESIGN.md`：界面约定
