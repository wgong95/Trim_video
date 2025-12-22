# Trim Video - 视频静音尾部裁剪工具

自动检测并裁剪视频末尾的静音部分，适用于批量处理录制视频、教程视频等含有多余静音尾部的文件。

## 功能特点

- 🔍 **自动检测静音**：使用 FFmpeg 的 silencedetect 滤镜精确定位视频末尾的静音起始点
- ⚡ **无损裁剪**：使用 stream copy 模式，不重新编码，处理速度极快
- 📁 **灵活处理**：支持单文件或整个目录批量处理
- 📂 **智能输出**：自动在源文件目录下创建 `trimmed/` 子目录存放输出文件

---

## 系统要求

- **Python**：3.6 或更高版本
- **FFmpeg**：必须安装并添加到系统 PATH

### 安装 FFmpeg

```bash
# macOS (使用 Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows (使用 Chocolatey)
choco install ffmpeg
```

---

## 使用方法

### 处理整个目录

处理指定目录下的所有 `.mkv` 文件：

```bash
python trim_video.py <目录路径>
```

**示例：**
```bash
python trim_video.py /Users/wgong/Downloads/合集·海底小纵队
```

输出文件保存到：`/Users/wgong/Downloads/合集·海底小纵队/trimmed/`

### 处理单个文件

使用 `-f` 开关处理单个 `.mkv` 文件：

```bash
python trim_video.py -f <文件路径>
```

**示例：**
```bash
python trim_video.py -f "/Users/wgong/Downloads/合集·海底小纵队/001 - 【海底小纵队第一季】1海底小纵队与海底风暴.mkv"
```

输出文件保存到：`/Users/wgong/Downloads/合集·海底小纵队/trimmed/`

---

## 配置参数

脚本顶部定义了可调整的配置参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SILENCE_THRESHOLD` | `-40dB` | 静音阈值，低于此音量视为静音 |
| `MIN_SILENCE_DURATION` | `2.0` | 最小静音持续时间（秒），避免误检短暂静音 |

### 调整静音检测灵敏度

- **更敏感**（检测更轻的声音为静音）：将阈值调高，如 `-30dB`
- **更宽松**（只检测完全静音）：将阈值调低，如 `-50dB`

```python
# 示例：调整配置
SILENCE_THRESHOLD = "-30dB"  # 更敏感
MIN_SILENCE_DURATION = 1.0   # 缩短最小静音时长
```

---

## 技术实现

### 工作流程

```
1. 扫描目录/文件
       ↓
2. FFmpeg silencedetect 分析音频
       ↓
3. 解析输出，提取最后一个 silence_start 时间戳
       ↓
4. 使用 FFmpeg -to 参数裁剪到静音起始点
       ↓
5. Stream copy 输出到 trimmed/ 目录
```

### 核心函数

#### `detect_last_silence_start(video)`

使用 FFmpeg 的 `silencedetect` 音频滤镜检测静音段：

```bash
ffmpeg -i video.mkv -af "silencedetect=n=-40dB:d=2.0" -f null -
```

解析 stderr 输出中的 `silence_start` 时间戳，返回**最后一个**静音起始时间。

#### `process_file(mkv_path, out_dir)`

执行实际的裁剪操作：

```bash
ffmpeg -loglevel error -i input.mkv -to <silence_start> -c copy output.mkv
```

- `-to`：指定输出的结束时间
- `-c copy`：流复制模式，不重新编码

### 正则表达式

```python
SILENCE_RE = re.compile(r"silence_start: ([0-9.]+)|silence_end: ([0-9.]+)")
```

匹配 FFmpeg 输出中的静音检测结果：
- `silence_start: 580.234` - 静音开始时间
- `silence_end: 600.000` - 静音结束时间

---

## 输出示例

```
$ python trim_video.py /Users/wgong/Downloads/合集·海底小纵队

Found 50 .mkv file(s) in '/Users/wgong/Downloads/合集·海底小纵队'
Processing: 001 - 【海底小纵队第一季】1海底小纵队与海底风暴.mkv
  Trimmed at 623.45s → /Users/wgong/Downloads/合集·海底小纵队/trimmed/001 - ...
Processing: 002 - 【海底小纵队第一季】2海底小纵队与大王乌贼.mkv
  Trimmed at 618.32s → /Users/wgong/Downloads/合集·海底小纵队/trimmed/002 - ...
Processing: 003 - 【海底小纵队第一季】3海底小纵队与海象首领.mkv
  No silence detected → skipped
Done.
```

---

## 注意事项

1. **文件格式**：当前仅支持 `.mkv` 格式
2. **覆盖警告**：如果 `trimmed/` 目录中已存在同名文件，会被覆盖
3. **无静音视频**：如果未检测到符合条件的静音段，文件将被跳过
4. **磁盘空间**：确保有足够空间存放输出文件

---

## 常见问题

### Q: 为什么某些文件显示 "No silence detected"？

可能原因：
- 视频末尾没有超过 2 秒的静音
- 末尾有背景噪音高于 -40dB
- 尝试调低 `MIN_SILENCE_DURATION` 或调高 `SILENCE_THRESHOLD`

### Q: 如何支持其他视频格式？

修改 `glob` 模式即可：

```python
# 支持 mp4
mkv_files = list(input_path.glob("*.mp4"))

# 支持多种格式
mkv_files = list(input_path.glob("*.mkv")) + list(input_path.glob("*.mp4"))
```

### Q: 处理速度慢怎么办？

静音检测需要解码整个音频流，这是主要耗时部分。裁剪本身（stream copy）非常快。

---

## 许可证

MIT License
