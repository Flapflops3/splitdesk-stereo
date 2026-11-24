# 安装、试听与故障定位

## 1. 准备主机和客户端

- 主机为 Windows 11 x64，安装目录需要可写，首次安装需要访问 GitHub、Python 下载服务和 PyPI。已验证的 Sunshine Windows 程序文件版本为 **2026.1123.40502**。其他版本请在上游文档确认支持 **external_audio**。如果发行版尚未提供该参数，可从官方 Releases 选择支持它的版本。
- 从官方渠道在主机安装 Sunshine、在左侧设备安装 Moonlight。先在同一局域网内配对，Moonlight 显示 PIN 后在 Sunshine Web UI 的 PIN 页输入；先验证普通 Desktop 串流能显示画面和播放声音。 [Sunshine Releases](https://github.com/LizardByte/Sunshine/releases) · [Moonlight Setup Guide](https://github.com/moonlight-stream/moonlight-docs/wiki/Setup-Guide)
- 从 VB-Audio 下载标准 **VB-CABLE** Windows 压缩包，解压，以管理员身份运行 x64 setup，选择 Install Driver，按提示重启。在 Windows 声音面板应同时可见播放端点和录制端点。 [VB-CABLE 官网](https://vb-audio.com/Cable/)
- 准备与 VB-CABLE 分开的虚拟播放端点。实测使用 **Steam Streaming Speakers**。可先在安装 Steam 的主机完成一次 Steam Remote Play 并按提示安装音频驱动，或在 Sunshine 普通音频模式下使用其 Steam 驱动安装功能。用 `mmsys.cpl` 确认该播放设备已启用，再设置 external_audio。 [Sunshine 音频设置](https://docs.lizardbyte.dev/projects/sunshine/master/md_docs_2configuration.html)

## 2. 安装与设备命名

从 Release 下载 Windows x64 ZIP 并完整解压。双击 `Install.cmd`。它在当前用户的 `%LOCALAPPDATA%\SplitDeskStereo` 创建 Python 3.14 虚拟环境、安装固定版本依赖并创建桌面入口。首次运行会显示 Devices。安装驱动需要管理员权限，调音台本身用普通用户运行。

| Devices 字段 | 怎么选 |
| --- | --- |
| Left device name | 填客户端实际设备名，例如 Nova。Windows 的串流音频端点通常只显示驱动名，因此需要输入。 |
| Right device name | 默认读取 Windows 计算机名，也可填自己的设备名。 |
| Windows mix | VB-CABLE 的播放侧，通常是 CABLE Input，部分系统显示为 Speakers / 扬声器 (VB-Audio Virtual Cable)。 |
| Cable return | 同一条线的录制侧，通常为 CABLE Output。 |
| Left · Sunshine capture endpoint | Steam Streaming Speakers。 |
| Right · Physical speakers | 主机内置扬声器、显示器音箱或实际使用的有线声卡。 |
| Right channel delay | 先用 35 ms，试听后再调整。 |

保存时会在安装目录生成 `routing.json` 和 `sunshine-audio.txt`。端点 ID 只适用于本机。更换声卡、重装驱动或换电脑后重新选择。可运行安装目录的 `Check.cmd` 检查端点和 48 kHz 立体声输出格式。

## 3. 让 Sunshine 只捕获左声道

1. 结束当前串流，备份**正在运行的 Sunshine 实例**的 `sunshine.conf`。Windows 标准安装通常位于 Sunshine 安装目录的 `config` 子目录，便携版使用自己的配置目录。
2. 打开生成的 `sunshine-audio.txt`。把其中的 `external_audio = enabled` 和 `audio_sink = …` 两行写入上面的配置文件。同名项应替换，保留其他已有设置。第二行的值是左侧串流端点的完整 ID。
3. 保存并重启对应的 Sunshine 服务或便携实例。此设置对该实例的应用生效。如果同时保留普通桌面音频模式，使用独立配置的 Sunshine 实例并为其设置不同的端口。 [Sunshine 配置参考](https://docs.lizardbyte.dev/projects/sunshine/master/md_docs_2configuration.html)
4. 在 Moonlight 选择立体声音频并连接 Desktop。打开调音台点 **Start split**。Windows 的控制台和多媒体默认输出自动切到 VB-CABLE；音乐播放器选择 **Default / 系统默认**。Windows 的“通信”输出单独保留。
5. 用完点 **Stop split**。关闭调音台窗口、断开 Moonlight 或退出托盘图标，都不会代替这一步。断流后仍可从桌面入口重新打开调音台，或运行安装目录下的 `Stop.cmd`。

## 4. 试听与延迟校准

1. 调低两台设备音量，播放安装目录里的 `Test stereo.wav`。前两声 880 Hz 短音应只从左边出现，后面一声 440 Hz 长音只从右边出现。
2. 分别按两个 **Mute**，确认消失的声音与设备名一致。两路推子控制 Windows 侧的输出；客户端的系统音量和蓝牙耳机选择仍由客户端管理。
3. 用人声居中的单声道录音调左右音量，使人声听起来位于两台设备之间。再用单声道节拍试听同步。如果主机声先到，先 Stop split，在 Devices 将 Right channel delay 增加 5–10 ms，保存并重新 Start split。主机声后到则减小。支持 0–300 ms，网络和蓝牙延迟变化后可能需要重调。
4. 在 Master EQ 选择 Flat、Jazz、Pop、Rock 或 Vocal。Bypass 便于比较。Track Mixer 用于本地文件；载入同步分轨后可独听、静音或调整各轨，也可混合多声道文件再交给左右两路。

## 5. 从哪一段查故障

| 现象 | 检查与处理 |
| --- | --- |
| 找不到设备或无法启动 | 打开 `mmsys.cpl`，检查播放和录制设备是否启用。从安装目录运行 Check.cmd。将重复名称的 WASAPI 播放设备改为不同名称，在 Devices 重新保存。 |
| 只有电脑响，播放应用绕过调音台 | Windows 设置 → 系统 → 声音 → 音量混合器，把播放应用的输出设为“默认”。Apple Music 还可能有单独的 AMPLibraryAgent 播放会话。播放音乐时检查这些会话；必要时退出并重开播放器。 |
| 左电平表在动，客户端无声 | 确认客户端媒体音量、实际蓝牙输出和 Moonlight 音频。查看 Sunshine 日志里的 `Capturing audio from sink` 是否等于生成的 audio_sink，以及 `Opus initialized` 是否出现。确认连接的是改过配置的实例。 |
| 两侧都没声 | 先在普通 Desktop 串流试听，再检查 Start split、VB-CABLE 输入/输出配对、应用和端点静音。可以用测试 WAV 替换播放源。 |
| 断音、声像漂移或回声 | 先用稳定局域网和有线/内置扬声器。检查 VB-CABLE 录制端点的“侦听此设备”是否导致重复监听；关闭其他重复路由后再调右声道延迟。 |
| 异常退出、默认输出仍是虚拟线 | 运行 Stop.cmd。它只在默认值仍指向本工具的虚拟线时恢复之前保存的设备。如果原设备已拔出，重新选择 Windows 的实体扬声器。 |
| 需要日志 | 安装目录的 routing.log 记录路由错误；启动异常看 startup.log。分享前删除机器路径、设备 ID 和配对信息。 |

## 升级、登录启动与卸载

升级前停止路由、关闭调音台，并右击托盘图标选择 Quit Tray。解压新版并重跑 Install.cmd。安装过程保留本机 routing.json 和 mix-controls.json。默认创建桌面快捷方式。若希望登录时仅加载原生托盘，在解压目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\install.ps1 -StartAtLogin
```

卸载时先 Stop split、退出界面和托盘，恢复备份的 Sunshine 配置并重启 Sunshine。删除桌面/启动文件夹中的 SplitDesk Stereo 快捷方式及本工具安装目录即可。VB-CABLE 或 Steam 音频驱动若被其他程序使用可继续保留；如需移除，使用厂商的卸载方式。

从源码复建原生组件的方法见[英文构建说明](SETUP.md#native-build-and-source-run)。
