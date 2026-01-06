# WebCodecs 快速验证 Demo

**目标**: 1-2天内验证WebCodecs核心技术可行性
**难度**: ⭐⭐⭐ (中等)

---

## 🎯 Demo目标

验证以下核心功能：
1. ✅ 视频文件读取
2. ✅ 视频解码为帧
3. ✅ Canvas画面合成
4. ✅ 视频编码
5. ✅ 下载输出文件

---

## 🚀 最小可行Demo (100行代码)

创建一个HTML文件即可运行：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WebCodecs 视频合并 Demo</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 800px;
      margin: 50px auto;
      padding: 20px;
    }
    .file-input {
      margin: 20px 0;
    }
    button {
      padding: 10px 20px;
      font-size: 16px;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    video {
      width: 100%;
      margin: 20px 0;
    }
    .progress {
      margin: 20px 0;
    }
    progress {
      width: 100%;
      height: 30px;
    }
    .log {
      background: #f5f5f5;
      padding: 10px;
      border-radius: 5px;
      max-height: 300px;
      overflow-y: auto;
      font-family: monospace;
      font-size: 12px;
    }
  </style>
</head>
<body>
  <h1>🎬 WebCodecs 视频合并 Demo</h1>

  <p><strong>浏览器兼容性检测:</strong>
    <span id="compatibility"></span>
  </p>

  <div class="file-input">
    <label>
      视频1 (左侧):
      <input type="file" id="video1" accept="video/mp4">
    </label>
  </div>

  <div class="file-input">
    <label>
      视频2 (右侧):
      <input type="file" id="video2" accept="video/mp4">
    </label>
  </div>

  <button id="processBtn" disabled>开始合并</button>

  <div class="progress" id="progressContainer" style="display: none;">
    <progress id="progress" value="0" max="100"></progress>
    <span id="progressText">0%</span>
  </div>

  <div id="output" style="display: none;">
    <h3>处理结果:</h3>
    <video id="outputVideo" controls></video>
    <button id="downloadBtn">下载视频</button>
  </div>

  <div class="log" id="log"></div>

  <script type="module">
    // ============================================
    // 日志工具
    // ============================================
    function log(message) {
      const logDiv = document.getElementById('log');
      const time = new Date().toLocaleTimeString();
      logDiv.innerHTML += `[${time}] ${message}<br>`;
      logDiv.scrollTop = logDiv.scrollHeight;
      console.log(message);
    }

    // ============================================
    // 兼容性检测
    // ============================================
    function checkCompatibility() {
      const hasVideoDecoder = typeof VideoDecoder !== 'undefined';
      const hasVideoEncoder = typeof VideoEncoder !== 'undefined';
      const compatible = hasVideoDecoder && hasVideoEncoder;

      const compatDiv = document.getElementById('compatibility');
      if (compatible) {
        compatDiv.innerHTML = '<span style="color: green;">✅ 支持 WebCodecs</span>';
        log('✅ 浏览器支持 WebCodecs API');
      } else {
        compatDiv.innerHTML = '<span style="color: red;">❌ 不支持 WebCodecs (请使用 Chrome 94+)</span>';
        log('❌ 浏览器不支持 WebCodecs API');
      }

      return compatible;
    }

    // ============================================
    // 简单的视频处理器
    // ============================================
    class SimpleVideoMerger {
      async merge(file1, file2, onProgress) {
        log('开始处理视频...');

        // 1. 读取视频信息
        log('步骤1: 读取视频信息');
        const [info1, info2] = await Promise.all([
          this.getVideoInfo(file1),
          this.getVideoInfo(file2)
        ]);

        log(`视频1: ${info1.width}x${info1.height}, 时长: ${info1.duration.toFixed(2)}s`);
        log(`视频2: ${info2.width}x${info2.height}, 时长: ${info2.duration.toFixed(2)}s`);

        // 2. 创建视频元素并解码
        log('步骤2: 解码视频帧');
        const frames1 = await this.extractFrames(file1, 30); // 提取30帧
        const frames2 = await this.extractFrames(file2, 30);

        log(`提取到 ${frames1.length} 和 ${frames2.length} 帧`);
        onProgress(30);

        // 3. 合成画面
        log('步骤3: 合成画面');
        const outputWidth = info1.width;
        const outputHeight = info1.height;
        const canvas = new OffscreenCanvas(outputWidth, outputHeight);
        const ctx = canvas.getContext('2d', { alpha: false });

        const composedFrames = [];
        const frameCount = Math.min(frames1.length, frames2.length);

        for (let i = 0; i < frameCount; i++) {
          // 左右分割
          const leftWidth = Math.floor(outputWidth * 0.5);

          // 绘制左侧
          ctx.drawImage(frames1[i], 0, 0, leftWidth, outputHeight);

          // 绘制右侧
          ctx.drawImage(frames2[i], leftWidth, 0, outputWidth - leftWidth, outputHeight);

          // 创建新帧
          const timestamp = i * (1000000 / 30); // 微秒
          const newFrame = new VideoFrame(canvas, { timestamp });
          composedFrames.push(newFrame);

          onProgress(30 + (i / frameCount) * 30);
        }

        log(`合成了 ${composedFrames.length} 帧`);
        onProgress(60);

        // 4. 编码视频
        log('步骤4: 编码视频');
        const chunks = [];
        const encoder = new VideoEncoder({
          output: (chunk) => chunks.push(chunk),
          error: (e) => log('编码错误: ' + e)
        });

        encoder.configure({
          codec: 'avc1.42E01E',
          width: outputWidth,
          height: outputHeight,
          bitrate: 3000000,
          framerate: 30
        });

        for (let i = 0; i < composedFrames.length; i++) {
          const keyFrame = i % 30 === 0;
          encoder.encode(composedFrames[i], { keyFrame });
          composedFrames[i].close();

          onProgress(60 + (i / composedFrames.length) * 30);
        }

        await encoder.flush();
        encoder.close();

        log(`编码了 ${chunks.length} 个视频块`);
        onProgress(90);

        // 5. 简单封装（实际需要用mp4-muxer）
        log('步骤5: 创建输出视频');
        // 这里简化处理，实际项目需要用mp4-muxer
        const blob = await this.createMP4Blob(chunks, outputWidth, outputHeight);

        onProgress(100);
        log('✅ 处理完成！');

        // 清理
        frames1.forEach(f => f.close());
        frames2.forEach(f => f.close());

        return blob;
      }

      async getVideoInfo(file) {
        return new Promise((resolve) => {
          const video = document.createElement('video');
          video.preload = 'metadata';
          video.onloadedmetadata = () => {
            resolve({
              width: video.videoWidth,
              height: video.videoHeight,
              duration: video.duration
            });
          };
          video.src = URL.createObjectURL(file);
        });
      }

      async extractFrames(file, count) {
        return new Promise((resolve) => {
          const video = document.createElement('video');
          const frames = [];
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');

          video.onloadedmetadata = async () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            const duration = video.duration;
            const interval = duration / count;

            for (let i = 0; i < count; i++) {
              await new Promise((res) => {
                video.currentTime = i * interval;
                video.onseeked = () => {
                  ctx.drawImage(video, 0, 0);
                  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                  frames.push(canvas);
                  res();
                };
              });
            }

            resolve(frames);
          };

          video.src = URL.createObjectURL(file);
        });
      }

      async createMP4Blob(chunks, width, height) {
        // 简化版本：只返回raw数据
        // 实际项目需要使用 mp4-muxer 库正确封装
        const buffers = chunks.map(chunk => {
          const buffer = new ArrayBuffer(chunk.byteLength);
          chunk.copyTo(buffer);
          return buffer;
        });

        // 警告：这不是有效的MP4文件，仅用于Demo
        log('⚠️ 注意: 这是简化Demo，输出可能无法播放');
        log('⚠️ 完整项目需要使用 mp4-muxer 库');

        return new Blob(buffers, { type: 'video/mp4' });
      }
    }

    // ============================================
    // UI 逻辑
    // ============================================
    let file1 = null;
    let file2 = null;
    let outputBlob = null;

    document.getElementById('video1').addEventListener('change', (e) => {
      file1 = e.target.files[0];
      updateProcessButton();
    });

    document.getElementById('video2').addEventListener('change', (e) => {
      file2 = e.target.files[0];
      updateProcessButton();
    });

    function updateProcessButton() {
      const btn = document.getElementById('processBtn');
      btn.disabled = !(file1 && file2);
    }

    document.getElementById('processBtn').addEventListener('click', async () => {
      const btn = document.getElementById('processBtn');
      const progressContainer = document.getElementById('progressContainer');
      const outputDiv = document.getElementById('output');

      btn.disabled = true;
      progressContainer.style.display = 'block';
      outputDiv.style.display = 'none';

      try {
        const merger = new SimpleVideoMerger();

        outputBlob = await merger.merge(file1, file2, (progress) => {
          document.getElementById('progress').value = progress;
          document.getElementById('progressText').textContent = progress.toFixed(1) + '%';
        });

        // 显示结果
        const videoUrl = URL.createObjectURL(outputBlob);
        document.getElementById('outputVideo').src = videoUrl;
        outputDiv.style.display = 'block';

      } catch (error) {
        log('❌ 错误: ' + error.message);
        alert('处理失败: ' + error.message);
      } finally {
        btn.disabled = false;
      }
    });

    document.getElementById('downloadBtn').addEventListener('click', () => {
      if (!outputBlob) return;

      const url = URL.createObjectURL(outputBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'merged_video.mp4';
      a.click();
      URL.revokeObjectURL(url);

      log('✅ 视频已下载');
    });

    // 初始化
    if (checkCompatibility()) {
      log('准备就绪，请选择两个视频文件');
    }
  </script>
</body>
</html>
```

---

## 🎯 使用方法

1. **保存代码** - 将上面的代码保存为 `webcodecs_demo.html`
2. **打开文件** - 用 Chrome 94+ 浏览器打开
3. **选择视频** - 选择两个MP4视频文件（建议小文件，<10MB）
4. **点击合并** - 查看处理过程和结果

---

## ⚠️ Demo限制

这是一个**极简Demo**，有以下限制：

1. ❌ **不是完整的MP4封装** - 输出可能无法播放
2. ❌ **只提取30帧** - 演示用，实际应处理所有帧
3. ❌ **无音频处理** - 仅处理视频轨道
4. ❌ **简化的帧提取** - 使用video元素而非WebCodecs解码
5. ❌ **性能未优化** - 可能内存占用高

---

## ✅ Demo目标

这个Demo的目的是：

✅ **验证WebCodecs API可用** - 浏览器支持
✅ **验证基本流程** - 解码→合成→编码
✅ **验证性能** - 处理时间可接受
✅ **建立信心** - 技术方案可行

---

## 🚀 完整版本需要的改进

### 1. 使用mp4box.js解封装

```bash
npm install mp4box
```

```typescript
import MP4Box from 'mp4box';

// 完整的MP4解析，提取所有样本
const mp4boxFile = MP4Box.createFile();
mp4boxFile.onReady = (info) => {
  // 处理视频轨道
};
```

### 2. 使用mp4-muxer封装

```bash
npm install mp4-muxer
```

```typescript
import { Muxer, ArrayBufferTarget } from 'mp4-muxer';

const muxer = new Muxer({
  target: new ArrayBufferTarget(),
  video: {
    codec: 'avc',
    width: 1920,
    height: 1080
  }
});

// 添加视频块
muxer.addVideoChunk(chunk);

// 完成
const { buffer } = muxer.finalize();
```

### 3. 添加Web Worker

将处理逻辑放在Worker中，避免阻塞UI：

```typescript
// processor.worker.ts
self.onmessage = async (e) => {
  const { file1, file2, options } = e.data;

  // 处理视频
  const result = await processVideos(file1, file2, options);

  self.postMessage({ type: 'complete', result });
};
```

### 4. 内存管理

```typescript
// 及时释放帧
frame.close();

// 批量处理，避免内存溢出
const BATCH_SIZE = 30;
for (let i = 0; i < frames.length; i += BATCH_SIZE) {
  const batch = frames.slice(i, i + BATCH_SIZE);
  await processBatch(batch);
}
```

---

## 📊 预期结果

运行Demo后，你应该看到：

**成功指标**:
- ✅ 兼容性检测显示"支持WebCodecs"
- ✅ 能选择并读取视频文件
- ✅ 进度条从0%到100%
- ✅ 处理时间合理（小视频<10秒）
- ✅ 能显示输出视频（即使无法播放）
- ✅ 日志显示完整流程

**失败情况**:
- ❌ 浏览器不支持 → 升级到Chrome 94+
- ❌ 处理崩溃 → 尝试更小的视频
- ❌ 内存溢出 → 需要优化内存管理

---

## 🎯 验证完成后的下一步

如果Demo运行成功，说明技术方案可行，可以开始完整开发：

1. **Phase 1** (Week 1): 搭建React项目
2. **Phase 2** (Week 2-3): 集成mp4box.js和mp4-muxer
3. **Phase 3** (Week 4): 完整的处理流程
4. **Phase 4** (Week 5): UI开发
5. **Phase 5** (Week 6): 测试和优化

---

## 💡 常见问题

### Q: 为什么输出视频无法播放？

A: Demo中使用了简化的封装方式。完整项目需要使用mp4-muxer库正确封装MP4格式。

### Q: 处理大视频时浏览器崩溃？

A: 需要实现批量处理和及时释放内存。完整项目会处理这个问题。

### Q: Firefox/Safari支持吗？

A: 目前不支持。WebCodecs是Chrome特性，Firefox在开发中，Safari未计划支持。

### Q: 能处理多大的视频？

A: 取决于用户电脑性能和浏览器内存限制。建议限制在500MB以内。

---

## 📞 需要帮助？

如果Demo运行失败：

1. 检查浏览器版本（必须Chrome 94+）
2. 打开开发者工具查看Console错误
3. 尝试更小的视频文件（<10MB）
4. 确保视频是MP4格式

---

**准备好验证技术了吗？** 复制代码，立即开始！ 🚀
