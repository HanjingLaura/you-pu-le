# 有谱了

纯钢琴演奏视频（或音频）→ MIDI → 网页上的大谱表草稿。

四个界面：

- 校音：本机麦克风，实时音高
- 节拍：本机发声的节拍器
- 扒谱：钢琴独奏视频 / 音频 → MIDI → 大谱表草稿
- 移调：上传 MusicXML / MIDI，选原调和目标调，导出移调后的谱

扒谱仍是草稿谱，不是出版谱。装饰音、踏板、临时变音、左右手交叉都可能要再改。

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
