# WebCodecs 视频处理 Web 版实施指南

**创建日期**: 2026-01-05
**技术方案**: 基于 WebCodecs API 的纯客户端视频处理
**预计开发周期**: 6-8周
**运营成本**: $0-20/月

---

## 📋 目录

1. [方案概述](#方案概述)
2. [技术架构](#技术架构)
3. [开发流程](#开发流程)
4. [核心技术难点](#核心技术难点)
5. [详细实施步骤](#详细实施步骤)
6. [代码示例](#代码示例)
7. [测试计划](#测试计划)
8. [部署方案](#部署方案)

---

## 🎯 方案概述

### 核心特点

✅ **零服务器成本** - 完全客户端处理，无需后端服务器
✅ **高性能** - 硬件加速，比FFmpeg.wasm快5-10倍
✅ **隐私保护** - 视频文件不上传，完全本地处理
✅ **跨平台** - 基于浏览器，Windows/macOS/Linux通用

### 技术选型

```
前端框架: React 18 + TypeScript
视频处理: WebCodecs API (浏览器原生)
解封装: mp4box.js
封装: mp4-muxer
UI组件: Ant Design / Tailwind CSS
部署: Vercel / Netlify (免费)
```

### 浏览器兼容性

| 浏览器 | 最低版本 | 支持情况 |
|--------|----------|----------|
| Chrome | 94+ | ✅ 完全支持 |
| Edge | 94+ | ✅ 完全支持 |
| Opera | 80+ | ✅ 完全支持 |
| Firefox | 未支持 | ❌ 开发中 |
| Safari | 未支持 | ❌ 未计划 |

**目标用户覆盖率**: ~65%（Chrome + Edge用户）

---

## 🏗️ 技术架构

### 整体架构图

```
┌─────────────────────────────────────────────────────┐
│              React Web Application                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌───────────────────────────────────────────────┐ │
│  │         用户界面层 (UI Layer)                 │ │
│  │  - 文件选择                                   │ │
│  │  - 参数配置（分割方式、音频、封面）           │ │
│  │  - 实时进度显示                               │ │
│  │  - 预览和下载                                 │ │
│  └───────────────────────────────────────────────┘ │
│                       ↓                              │
│  ┌───────────────────────────────────────────────┐ │
│  │      视频处理引擎 (Processing Engine)        │ │
│  │                                               │ │
│  │  ┌──────────────┐  ┌──────────────┐         │ │
│  │  │ 解封装模块   │  │ 音频处理模块 │         │ │
│  │  │ (mp4box.js)  │  │ (WebCodecs)  │         │ │
│  │  └──────────────┘  └──────────────┘         │ │
│  │                                               │ │
│  │  ┌──────────────┐  ┌──────────────┐         │ │
│  │  │ 视频解码器   │  │ 视频编码器   │         │ │
│  │  │(VideoDecoder)│  │(VideoEncoder)│         │ │
│  │  └──────────────┘  └──────────────┘         │ │
│  │                                               │ │
│  │  ┌──────────────┐  ┌──────────────┐         │ │
│  │  │ 画布处理     │  │ 封装模块     │         │ │
│  │  │ (Canvas API) │  │ (mp4-muxer)  │         │ │
│  │  └──────────────┘  └──────────────┘         │ │
│  └───────────────────────────────────────────────┘ │
│                       ↓                              │
│  ┌───────────────────────────────────────────────┐ │
│  │      浏览器 API 层 (Browser APIs)             │ │
│  │  - File API (文件读取)                        │ │
│  │  - WebCodecs API (编解码)                     │ │
│  │  - Canvas API (画面合成)                      │ │
│  │  - Web Workers (多线程)                       │ │
│  └───────────────────────────────────────────────┘ │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 数据流程

```
用户选择视频文件
      ↓
读取文件 (File API)
      ↓
解封装 MP4 容器 (mp4box.js)
      ↓
提取视频轨道和音频轨道
      ↓
┌─────────────────┬─────────────────┐
│   视频流1       │    视频流2      │
│   (模板视频)    │   (列表视频)    │
└────────┬────────┴────────┬────────┘
         ↓                 ↓
    VideoDecoder     VideoDecoder
    (解码为帧)       (解码为帧)
         ↓                 ↓
    ┌────────────────────────┐
    │  Canvas 画布合成       │
    │  - 左右/上下分割       │
    │  - 按比例裁剪缩放      │
    └────────┬───────────────┘
             ↓
       VideoEncoder
       (编码新视频)
             ↓
    ┌────────────────┐
    │  音频处理      │
    │  - 静音        │
    │  - 保留原音    │
    │  - 混合        │
    └────────┬───────┘
             ↓
       mp4-muxer
       (封装为MP4)
             ↓
      Blob 对象
             ↓
      下载到本地
```

---

## 📈 开发流程

### Phase 1: 技术验证 (Week 1-2)

**目标**: 证明核心技术可行

**任务清单**:
- [ ] 搭建React + TypeScript项目
- [ ] 集成WebCodecs API基础功能
- [ ] 实现简单的视频解码Demo
- [ ] 实现简单的视频编码Demo
- [ ] 测试性能和内存占用
- [ ] 验证浏览器兼容性

**交付物**:
- 可运行的技术Demo
- 性能测试报告
- 技术可行性评估文档

**难度**: ⭐⭐⭐ (中等)

---

### Phase 2: 核心功能开发 (Week 3-4)

**目标**: 实现视频分割拼接核心功能

**任务清单**:
- [ ] 实现MP4解封装 (mp4box.js)
- [ ] 实现视频解码器
- [ ] 实现Canvas画面合成
  - [ ] 左右分割
  - [ ] 上下分割
  - [ ] 按比例裁剪
- [ ] 实现视频编码器
- [ ] 实现MP4封装 (mp4-muxer)
- [ ] 端到端测试

**交付物**:
- 完整的视频处理引擎
- 单元测试
- 性能优化报告

**难度**: ⭐⭐⭐⭐⭐ (非常高 - 最难部分)

---

### Phase 3: 音频处理 (Week 5)

**目标**: 实现音频配置功能

**任务清单**:
- [ ] 音频轨道提取
- [ ] 音频解码 (AudioDecoder)
- [ ] 音频混合
- [ ] 音频编码 (AudioEncoder)
- [ ] 音频与视频同步

**交付物**:
- 完整的音频处理模块
- 音频同步测试

**难度**: ⭐⭐⭐⭐ (高)

---

### Phase 4: UI/UX开发 (Week 6)

**目标**: 开发用户界面

**任务清单**:
- [ ] 文件选择界面
- [ ] 参数配置界面
  - [ ] 分割方式选择
  - [ ] 分割比例调整
  - [ ] 音频选项
- [ ] 进度显示
- [ ] 预览功能
- [ ] 下载功能
- [ ] 错误提示

**交付物**:
- 完整的Web应用界面
- 交互流程设计文档

**难度**: ⭐⭐ (简单)

---

### Phase 5: 封面和高级功能 (Week 7)

**目标**: 实现封面设置等高级功能

**任务清单**:
- [ ] 视频帧提取
- [ ] 封面预览
- [ ] 封面应用到输出视频
- [ ] 批量处理
- [ ] 视频信息显示

**交付物**:
- 高级功能模块
- 用户文档

**难度**: ⭐⭐⭐ (中等)

---

### Phase 6: 测试和优化 (Week 8)

**目标**: 全面测试和性能优化

**任务清单**:
- [ ] 功能测试（各种视频格式、分辨率）
- [ ] 性能测试（处理时间、内存占用）
- [ ] 兼容性测试（Chrome不同版本）
- [ ] 错误处理测试
- [ ] 用户体验测试
- [ ] 性能优化
- [ ] Bug修复

**交付物**:
- 测试报告
- 性能优化报告
- 生产就绪的应用

**难度**: ⭐⭐⭐ (中等)

---

## 🔥 核心技术难点

### 难点1: MP4解封装和封装 ⭐⭐⭐⭐⭐

**挑战**:
- MP4是复杂的容器格式
- 需要正确解析moov、mdat等atoms
- 时间戳处理复杂

**解决方案**:
- 使用成熟的库: mp4box.js (解封装)
- 使用成熟的库: mp4-muxer (封装)
- 不要自己实现解析器

**学习曲线**: 2-3天

**代码复杂度**: 高

---

### 难点2: 视频帧同步 ⭐⭐⭐⭐⭐

**挑战**:
- 两个视频可能帧率不同
- 需要精确对齐时间戳
- 音视频同步

**解决方案**:
```javascript
// 使用PTS (Presentation Timestamp) 对齐
const targetPTS = Math.floor(frameIndex * 1000000 / targetFrameRate);

// 从两个视频取相近时间戳的帧
const frame1 = getFrameByPTS(video1Frames, targetPTS);
const frame2 = getFrameByPTS(video2Frames, targetPTS);
```

**学习曲线**: 3-5天

**代码复杂度**: 非常高

---

### 难点3: Canvas画面合成性能 ⭐⭐⭐⭐

**挑战**:
- 1080p每帧2MB+数据
- 需要实时处理30fps
- 内存占用大

**解决方案**:
```javascript
// 使用OffscreenCanvas (Web Worker中)
const canvas = new OffscreenCanvas(1920, 1080);
const ctx = canvas.getContext('2d', {
  alpha: false,  // 禁用透明度，提升性能
  desynchronized: true  // 异步渲染
});

// 批量处理，避免频繁GC
const BATCH_SIZE = 30; // 每次处理30帧
```

**学习曲线**: 2-3天

**代码复杂度**: 中等

---

### 难点4: 内存管理 ⭐⭐⭐⭐⭐

**挑战**:
- VideoFrame占用大量内存
- 不及时释放会导致浏览器崩溃
- 需要手动调用close()

**解决方案**:
```javascript
// ❌ 错误做法 - 内存泄漏
function processFrame(frame) {
  const newFrame = doSomething(frame);
  return newFrame;
  // frame没有关闭，泄漏！
}

// ✅ 正确做法 - 及时释放
function processFrame(frame) {
  try {
    const newFrame = doSomething(frame);
    return newFrame;
  } finally {
    frame.close();  // 必须关闭！
  }
}
```

**学习曲线**: 1-2天

**代码复杂度**: 中等，但容易出错

---

### 难点5: 音频处理 ⭐⭐⭐⭐

**挑战**:
- 音频采样率不同需要重采样
- 音频混合算法
- 音视频同步

**解决方案**:
```javascript
// 音频混合（简单平均）
function mixAudio(samples1, samples2) {
  const mixed = new Float32Array(samples1.length);
  for (let i = 0; i < samples1.length; i++) {
    mixed[i] = (samples1[i] + samples2[i]) / 2;
  }
  return mixed;
}

// 使用AudioContext进行重采样
const audioContext = new AudioContext({
  sampleRate: 48000  // 统一采样率
});
```

**学习曲线**: 3-4天

**代码复杂度**: 高

---

### 难点6: 进度计算 ⭐⭐⭐

**挑战**:
- 解码、合成、编码各占不同时间
- 准确估算总进度

**解决方案**:
```javascript
// 权重分配
const WEIGHTS = {
  demux: 0.05,      // 解封装 5%
  decode: 0.25,     // 解码 25%
  compose: 0.30,    // 合成 30%
  encode: 0.35,     // 编码 35%
  mux: 0.05         // 封装 5%
};

function calculateProgress(stage, stageProgress) {
  let baseProgress = 0;
  for (const [key, weight] of Object.entries(WEIGHTS)) {
    if (key === stage) break;
    baseProgress += weight;
  }
  return baseProgress + WEIGHTS[stage] * stageProgress;
}
```

**学习曲线**: 1天

**代码复杂度**: 简单

---

## 📝 详细实施步骤

### Step 1: 项目初始化

```bash
# 创建React项目
npx create-react-app video-processor-web --template typescript
cd video-processor-web

# 安装依赖
npm install mp4box mp4-muxer
npm install antd  # 或者 npm install tailwindcss
npm install @types/mp4box --save-dev

# 配置SharedArrayBuffer响应头（WebCodecs需要）
# 在public目录创建_headers文件（Netlify）或vercel.json（Vercel）
```

**vercel.json**:
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Cross-Origin-Opener-Policy",
          "value": "same-origin"
        },
        {
          "key": "Cross-Origin-Embedder-Policy",
          "value": "require-corp"
        }
      ]
    }
  ]
}
```

---

### Step 2: 实现视频解封装

```typescript
// src/utils/demuxer.ts
import MP4Box from 'mp4box';

export interface VideoTrack {
  id: number;
  codec: string;
  width: number;
  height: number;
  duration: number;
  samples: any[];
}

export interface AudioTrack {
  id: number;
  codec: string;
  sampleRate: number;
  channels: number;
  samples: any[];
}

export class MP4Demuxer {
  private file: any;
  private videoTrack: VideoTrack | null = null;
  private audioTrack: AudioTrack | null = null;

  constructor() {
    this.file = MP4Box.createFile();
  }

  async demux(videoFile: File): Promise<{
    video: VideoTrack;
    audio: AudioTrack | null;
  }> {
    return new Promise((resolve, reject) => {
      this.file.onError = (e: any) => reject(e);

      this.file.onReady = (info: any) => {
        console.log('MP4 Info:', info);

        // 提取视频轨道
        const videoTrackInfo = info.videoTracks[0];
        if (videoTrackInfo) {
          this.videoTrack = {
            id: videoTrackInfo.id,
            codec: videoTrackInfo.codec,
            width: videoTrackInfo.video.width,
            height: videoTrackInfo.video.height,
            duration: info.duration / info.timescale,
            samples: []
          };

          this.file.setExtractionOptions(videoTrackInfo.id, null, {
            nbSamples: 1000000  // 提取所有样本
          });
        }

        // 提取音频轨道
        const audioTrackInfo = info.audioTracks[0];
        if (audioTrackInfo) {
          this.audioTrack = {
            id: audioTrackInfo.id,
            codec: audioTrackInfo.codec,
            sampleRate: audioTrackInfo.audio.sample_rate,
            channels: audioTrackInfo.audio.channel_count,
            samples: []
          };

          this.file.setExtractionOptions(audioTrackInfo.id, null, {
            nbSamples: 1000000
          });
        }

        this.file.start();
      };

      this.file.onSamples = (id: number, user: any, samples: any[]) => {
        if (this.videoTrack && id === this.videoTrack.id) {
          this.videoTrack.samples.push(...samples);
        }
        if (this.audioTrack && id === this.audioTrack.id) {
          this.audioTrack.samples.push(...samples);
        }
      };

      // 读取文件
      const reader = new FileReader();
      reader.onload = (e) => {
        const arrayBuffer = e.target!.result as ArrayBuffer;
        (arrayBuffer as any).fileStart = 0;
        this.file.appendBuffer(arrayBuffer);
        this.file.flush();

        // 解析完成
        resolve({
          video: this.videoTrack!,
          audio: this.audioTrack || null
        });
      };
      reader.readAsArrayBuffer(videoFile);
    });
  }
}
```

---

### Step 3: 实现视频解码器

```typescript
// src/utils/decoder.ts
import { VideoTrack } from './demuxer';

export class VideoDecoderWrapper {
  private decoder: VideoDecoder;
  private frames: VideoFrame[] = [];
  private onFrameCallback: ((frame: VideoFrame) => void) | null = null;

  constructor() {
    this.decoder = new VideoDecoder({
      output: (frame) => {
        if (this.onFrameCallback) {
          this.onFrameCallback(frame);
        } else {
          this.frames.push(frame);
        }
      },
      error: (error) => {
        console.error('Decoder error:', error);
      }
    });
  }

  configure(track: VideoTrack) {
    this.decoder.configure({
      codec: track.codec,
      codedWidth: track.width,
      codedHeight: track.height
    });
  }

  async decode(samples: any[]) {
    for (const sample of samples) {
      const chunk = new EncodedVideoChunk({
        type: sample.is_sync ? 'key' : 'delta',
        timestamp: sample.cts,
        duration: sample.duration,
        data: sample.data
      });

      this.decoder.decode(chunk);
    }

    await this.decoder.flush();
  }

  onFrame(callback: (frame: VideoFrame) => void) {
    this.onFrameCallback = callback;
  }

  getFrames(): VideoFrame[] {
    return this.frames;
  }

  close() {
    this.decoder.close();
    this.frames.forEach(frame => frame.close());
    this.frames = [];
  }
}
```

---

### Step 4: 实现画面合成

```typescript
// src/utils/composer.ts

export interface ComposerOptions {
  splitMode: 'horizontal' | 'vertical';  // 左右 or 上下
  splitRatio: number;  // 0.0 - 1.0
  outputWidth: number;
  outputHeight: number;
}

export class VideoComposer {
  private canvas: OffscreenCanvas;
  private ctx: OffscreenCanvasRenderingContext2D;

  constructor(private options: ComposerOptions) {
    this.canvas = new OffscreenCanvas(
      options.outputWidth,
      options.outputHeight
    );

    this.ctx = this.canvas.getContext('2d', {
      alpha: false,
      desynchronized: true
    })!;
  }

  compose(frame1: VideoFrame, frame2: VideoFrame): VideoFrame {
    const { splitMode, splitRatio, outputWidth, outputHeight } = this.options;

    if (splitMode === 'horizontal') {
      // 左右分割
      const leftWidth = Math.floor(outputWidth * splitRatio);
      const rightWidth = outputWidth - leftWidth;

      // 绘制左侧（frame1）
      this.ctx.drawImage(
        frame1,
        0, 0, frame1.displayWidth, frame1.displayHeight,  // 源
        0, 0, leftWidth, outputHeight  // 目标
      );

      // 绘制右侧（frame2）
      this.ctx.drawImage(
        frame2,
        0, 0, frame2.displayWidth, frame2.displayHeight,
        leftWidth, 0, rightWidth, outputHeight
      );
    } else {
      // 上下分割
      const topHeight = Math.floor(outputHeight * splitRatio);
      const bottomHeight = outputHeight - topHeight;

      // 绘制上方（frame1）
      this.ctx.drawImage(
        frame1,
        0, 0, frame1.displayWidth, frame1.displayHeight,
        0, 0, outputWidth, topHeight
      );

      // 绘制下方（frame2）
      this.ctx.drawImage(
        frame2,
        0, 0, frame2.displayWidth, frame2.displayHeight,
        0, topHeight, outputWidth, bottomHeight
      );
    }

    // 创建新的VideoFrame
    const newFrame = new VideoFrame(this.canvas, {
      timestamp: frame1.timestamp  // 使用frame1的时间戳
    });

    return newFrame;
  }
}
```

---

### Step 5: 实现视频编码器

```typescript
// src/utils/encoder.ts

export interface EncoderOptions {
  width: number;
  height: number;
  frameRate: number;
  bitrate: number;
}

export class VideoEncoderWrapper {
  private encoder: VideoEncoder;
  private chunks: EncodedVideoChunk[] = [];
  private onChunkCallback: ((chunk: EncodedVideoChunk) => void) | null = null;

  constructor(private options: EncoderOptions) {
    this.encoder = new VideoEncoder({
      output: (chunk, metadata) => {
        if (this.onChunkCallback) {
          this.onChunkCallback(chunk);
        } else {
          this.chunks.push(chunk);
        }
      },
      error: (error) => {
        console.error('Encoder error:', error);
      }
    });

    this.encoder.configure({
      codec: 'avc1.42E01E',  // H.264 Baseline
      width: options.width,
      height: options.height,
      bitrate: options.bitrate,
      framerate: options.frameRate,
      latencyMode: 'quality'
    });
  }

  encode(frame: VideoFrame, keyFrame: boolean = false) {
    this.encoder.encode(frame, { keyFrame });
  }

  async flush(): Promise<EncodedVideoChunk[]> {
    await this.encoder.flush();
    return this.chunks;
  }

  onChunk(callback: (chunk: EncodedVideoChunk) => void) {
    this.onChunkCallback = callback;
  }

  close() {
    this.encoder.close();
  }
}
```

---

### Step 6: 实现MP4封装

```typescript
// src/utils/muxer.ts
import { Muxer, ArrayBufferTarget } from 'mp4-muxer';

export class MP4Muxer {
  private muxer: Muxer<ArrayBufferTarget>;

  constructor(
    width: number,
    height: number,
    frameRate: number
  ) {
    this.muxer = new Muxer({
      target: new ArrayBufferTarget(),
      video: {
        codec: 'avc',
        width,
        height
      },
      fastStart: 'in-memory'
    });
  }

  addVideoChunk(chunk: EncodedVideoChunk, timestamp: number) {
    this.muxer.addVideoChunk(chunk, {
      duration: 1000000 / 30  // 微秒
    });
  }

  finalize(): Blob {
    this.muxer.finalize();
    const buffer = (this.muxer.target as ArrayBufferTarget).buffer;
    return new Blob([buffer], { type: 'video/mp4' });
  }
}
```

---

### Step 7: 整合处理流程

```typescript
// src/utils/processor.ts
import { MP4Demuxer } from './demuxer';
import { VideoDecoderWrapper } from './decoder';
import { VideoComposer } from './composer';
import { VideoEncoderWrapper } from './encoder';
import { MP4Muxer } from './muxer';

export interface ProcessOptions {
  splitMode: 'horizontal' | 'vertical';
  splitRatio: number;
  onProgress?: (progress: number) => void;
}

export class VideoProcessor {
  async process(
    templateFile: File,
    listFile: File,
    options: ProcessOptions
  ): Promise<Blob> {
    const { splitMode, splitRatio, onProgress } = options;

    // 1. 解封装 (5%)
    onProgress?.(0);
    const demuxer1 = new MP4Demuxer();
    const demuxer2 = new MP4Demuxer();

    const [video1, video2] = await Promise.all([
      demuxer1.demux(templateFile),
      demuxer2.demux(listFile)
    ]);

    onProgress?.(5);

    // 2. 解码 (5% -> 30%)
    const decoder1 = new VideoDecoderWrapper();
    const decoder2 = new VideoDecoderWrapper();

    decoder1.configure(video1.video);
    decoder2.configure(video2.video);

    const frames1: VideoFrame[] = [];
    const frames2: VideoFrame[] = [];

    decoder1.onFrame(frame => frames1.push(frame));
    decoder2.onFrame(frame => frames2.push(frame));

    await Promise.all([
      decoder1.decode(video1.video.samples),
      decoder2.decode(video2.video.samples)
    ]);

    onProgress?.(30);

    // 3. 合成 (30% -> 60%)
    const composer = new VideoComposer({
      splitMode,
      splitRatio,
      outputWidth: video1.video.width,
      outputHeight: video1.video.height
    });

    const composedFrames: VideoFrame[] = [];
    const totalFrames = Math.min(frames1.length, frames2.length);

    for (let i = 0; i < totalFrames; i++) {
      const composed = composer.compose(frames1[i], frames2[i]);
      composedFrames.push(composed);

      // 释放源帧
      frames1[i].close();
      frames2[i].close();

      // 更新进度
      const progress = 30 + (i / totalFrames) * 30;
      onProgress?.(progress);
    }

    // 4. 编码 (60% -> 90%)
    const encoder = new VideoEncoderWrapper({
      width: video1.video.width,
      height: video1.video.height,
      frameRate: 30,
      bitrate: 5000000  // 5 Mbps
    });

    for (let i = 0; i < composedFrames.length; i++) {
      const isKeyFrame = i % 30 === 0;  // 每30帧一个关键帧
      encoder.encode(composedFrames[i], isKeyFrame);

      // 释放合成帧
      composedFrames[i].close();

      const progress = 60 + (i / composedFrames.length) * 30;
      onProgress?.(progress);
    }

    const chunks = await encoder.flush();
    onProgress?.(90);

    // 5. 封装 (90% -> 100%)
    const muxer = new MP4Muxer(
      video1.video.width,
      video1.video.height,
      30
    );

    for (let i = 0; i < chunks.length; i++) {
      muxer.addVideoChunk(chunks[i], i * (1000000 / 30));

      const progress = 90 + (i / chunks.length) * 10;
      onProgress?.(progress);
    }

    const outputBlob = muxer.finalize();
    onProgress?.(100);

    // 清理
    decoder1.close();
    decoder2.close();
    encoder.close();

    return outputBlob;
  }
}
```

---

### Step 8: React组件实现

```typescript
// src/App.tsx
import React, { useState } from 'react';
import { VideoProcessor } from './utils/processor';

function App() {
  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [listFile, setListFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [outputUrl, setOutputUrl] = useState<string | null>(null);

  const handleProcess = async () => {
    if (!templateFile || !listFile) {
      alert('请选择两个视频文件');
      return;
    }

    setProcessing(true);
    setProgress(0);

    try {
      const processor = new VideoProcessor();

      const outputBlob = await processor.process(
        templateFile,
        listFile,
        {
          splitMode: 'horizontal',
          splitRatio: 0.5,
          onProgress: (p) => setProgress(p)
        }
      );

      const url = URL.createObjectURL(outputBlob);
      setOutputUrl(url);

      alert('处理完成！');
    } catch (error) {
      console.error('处理失败:', error);
      alert('处理失败: ' + error);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="App">
      <h1>视频分割拼接工具 - Web版</h1>

      <div>
        <h3>1. 选择模板视频</h3>
        <input
          type="file"
          accept="video/mp4"
          onChange={(e) => setTemplateFile(e.target.files?.[0] || null)}
        />
      </div>

      <div>
        <h3>2. 选择列表视频</h3>
        <input
          type="file"
          accept="video/mp4"
          onChange={(e) => setListFile(e.target.files?.[0] || null)}
        />
      </div>

      <div>
        <button
          onClick={handleProcess}
          disabled={!templateFile || !listFile || processing}
        >
          {processing ? '处理中...' : '开始处理'}
        </button>
      </div>

      {processing && (
        <div>
          <progress value={progress} max={100} />
          <span>{progress.toFixed(1)}%</span>
        </div>
      )}

      {outputUrl && (
        <div>
          <h3>处理完成</h3>
          <video src={outputUrl} controls width="640" />
          <br />
          <a href={outputUrl} download="merged.mp4">
            <button>下载视频</button>
          </a>
        </div>
      )}
    </div>
  );
}

export default App;
```

---

## 🧪 测试计划

### 功能测试

| 测试项 | 输入 | 预期输出 | 优先级 |
|--------|------|----------|--------|
| 基础合并 | 2个1080p MP4 | 合并后的MP4 | P0 |
| 左右分割 | 比例0.5 | 左右各占50% | P0 |
| 上下分割 | 比例0.3 | 上30%下70% | P0 |
| 不同分辨率 | 720p + 1080p | 自动缩放 | P1 |
| 不同时长 | 10s + 5s | 输出5秒 | P1 |
| 无音频视频 | 静音视频 | 正常处理 | P1 |

### 性能测试

| 场景 | 视频规格 | 期望处理时间 |
|------|----------|--------------|
| 小视频 | 720p 10秒 | < 5秒 |
| 中视频 | 1080p 30秒 | < 20秒 |
| 大视频 | 1080p 2分钟 | < 1分钟 |

### 兼容性测试

| 浏览器 | 版本 | 测试状态 |
|--------|------|----------|
| Chrome | 94+ | ✅ 必测 |
| Chrome | 100+ | ✅ 必测 |
| Chrome | 120+ | ✅ 必测 |
| Edge | 94+ | ✅ 必测 |
| Opera | 80+ | ⚠️ 可选 |

---

## 🚀 部署方案

### 方案1: Vercel（推荐）

**优点**:
- 免费
- 自动部署
- 全球CDN
- 零配置

**步骤**:
```bash
# 1. 安装Vercel CLI
npm i -g vercel

# 2. 登录
vercel login

# 3. 部署
vercel --prod
```

**配置文件** (vercel.json):
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Cross-Origin-Opener-Policy",
          "value": "same-origin"
        },
        {
          "key": "Cross-Origin-Embedder-Policy",
          "value": "require-corp"
        }
      ]
    }
  ]
}
```

---

### 方案2: Netlify

**优点**:
- 免费
- 简单易用
- 持续部署

**步骤**:
```bash
# 1. 构建
npm run build

# 2. 在Netlify网站上传dist文件夹
# 或使用CLI
npm i -g netlify-cli
netlify deploy --prod
```

**配置文件** (_headers):
```
/*
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Embedder-Policy: require-corp
```

---

### 方案3: GitHub Pages

**优点**:
- 免费
- 与代码库集成

**缺点**:
- 不支持自定义响应头（WebCodecs需要）

**不推荐**，除非使用Service Worker hack。

---

## 📊 总体评估

### 开发难度评分

| 模块 | 难度 | 工作量(天) | 风险 |
|------|------|-----------|------|
| 项目搭建 | ⭐ | 1 | 低 |
| MP4解封装 | ⭐⭐⭐ | 3 | 中 |
| 视频解码 | ⭐⭐⭐⭐ | 4 | 高 |
| 画面合成 | ⭐⭐⭐ | 3 | 中 |
| 视频编码 | ⭐⭐⭐⭐ | 4 | 高 |
| MP4封装 | ⭐⭐⭐ | 3 | 中 |
| 音频处理 | ⭐⭐⭐⭐ | 5 | 高 |
| UI开发 | ⭐⭐ | 3 | 低 |
| 测试优化 | ⭐⭐⭐ | 4 | 中 |
| **总计** | - | **30天** | - |

### 成功关键因素

✅ **使用成熟的库** - mp4box.js, mp4-muxer
✅ **严格的内存管理** - 及时释放VideoFrame
✅ **详细的日志** - 便于调试
✅ **渐进式开发** - 先实现基础功能
✅ **充分测试** - 各种视频格式和分辨率

### 潜在风险

⚠️ **浏览器兼容性** - 只支持Chrome/Edge
⚠️ **性能问题** - 大文件可能慢
⚠️ **内存限制** - 浏览器可能崩溃
⚠️ **编解码器限制** - 某些格式不支持

---

## 🎯 下一步行动

### 立即开始（本周）

1. **搭建项目** - 使用create-react-app
2. **技术验证** - 实现简单的解码->画布->编码Demo
3. **性能测试** - 测试处理时间和内存占用

### 2周内

4. **核心功能开发** - 完整的处理流程
5. **UI开发** - 基础界面

### 1个月内

6. **音频处理** - 添加音频支持
7. **高级功能** - 封面、批量处理
8. **测试部署** - 上线测试版本

---

## 📞 需要帮助？

如果在实施过程中遇到问题：

1. **技术问题** - 查看WebCodecs官方文档
2. **库使用问题** - 查看mp4box.js和mp4-muxer文档
3. **性能问题** - 使用Chrome DevTools分析
4. **调试技巧** - 添加详细console.log

---

**准备好开始了吗？** 🚀

建议从**技术验证Demo**开始，用1-2天时间证明核心流程可行，再投入完整开发！
