# Windows installation and troubleshooting

## Requirements

Use a Windows x64 host, a paired Moonlight client on the LAN, standard VB-CABLE and a separate virtual render device for the stream. The original two-device listening test used an iPad and a Windows notebook. The Sunshine executable tested was 2026.1123.40502. Check that your build supports Windows capture-only mode (`external_audio`).

1. Install [Sunshine](https://github.com/LizardByte/Sunshine/releases) and [Moonlight](https://github.com/moonlight-stream/moonlight-docs/wiki/Setup-Guide). Enter the PIN shown by Moonlight in Sunshine’s pairing page. Verify ordinary desktop streaming and audio first.
2. Download and extract [VB-CABLE](https://vb-audio.com/Cable/). Run its Windows x64 installer as administrator and reboot when requested. Check both playback and recording tabs in `mmsys.cpl`.
3. For the separate streaming endpoint, the tested option is Steam Streaming Speakers. Complete a Steam Remote Play session and accept its driver installation, or install Steam’s audio driver through Sunshine before enabling capture-only mode. Confirm the endpoint exists. [Sunshine configuration](https://docs.lizardbyte.dev/projects/sunshine/master/md_docs_2configuration.html)
4. Extract the full Windows x64 release ZIP. Double-click `Install.cmd`. It installs under `%LOCALAPPDATA%\SplitDeskStereo` and creates a desktop shortcut. Internet is needed for the per-user Python environment and pinned packages. Drivers and streaming apps are installed separately.

## Name the devices and route audio

Open the mixer. Enter the actual name of the **left** Moonlight device. The **right** name defaults to the Windows computer name. Select the standard VB-CABLE playback endpoint as Windows mix, its recording endpoint as Cable return, Steam Streaming Speakers as left output and the physical host speakers as right output. Start with 35 ms of right delay. Save. Run `Check.cmd` in the installation folder to validate WASAPI outputs at 48 kHz stereo.

End the stream and back up the active Sunshine instance’s `sunshine.conf`. Copy the two lines from the generated `sunshine-audio.txt` into that config, replacing existing values for the same keys. They set `external_audio = enabled` and `audio_sink` to the selected streaming endpoint ID. Restart the corresponding Sunshine instance. These settings apply to the instance; use a separately configured instance if you also need ordinary Sunshine audio.

Connect Moonlight with stereo audio, then click **Start split**. The router takes the current console and multimedia defaults, opens the two outputs and switches Windows playback to the mix cable. Set source applications to follow the system default. Click **Stop split** at the end of the session. The routing process is independent of the mixer window and Moonlight disconnects. **Stop.cmd** can stop it or recover the saved Windows outputs after an abnormal exit.

## Verify and tune

Play **Test stereo.wav** at a low level. Listen for two short high pulses on the left, then one longer low pulse on the right. Test the mute buttons separately. Balance the faders with a centered mono voice. For timing, use a mono click: increase the right delay if the host arrives first; decrease it if the host arrives late. Stop the route, adjust Devices by 5–10 ms, save and restart the route. The available range is 0–300 ms. Bluetooth and changing network buffers affect alignment.

Flat, Jazz, Pop, Rock and Vocal are adjustable starting points. EQ is applied once before the split and reserves output headroom. The curve shows filter gain before output trim. To control vocals or instruments independently, import aligned stems or load a file with separate audio tracks in Track Mixer.

## Troubleshooting

- **Missing devices or duplicate WASAPI names.** Enable the render/record endpoints in Windows, give duplicate render names distinct labels, revisit Devices and run Check.cmd.
- **Host only.** Check Windows Settings → System → Sound → Volume mixer. The source app must follow Default. Apple Music can play through a separate AMPLibraryAgent session. Restart the source after correcting its output.
- **The left meter moves but the client is quiet.** Check the client media volume, Bluetooth destination and Moonlight audio settings. Match Sunshine’s log entry `Capturing audio from sink` to the selected endpoint. Check for Opus initialization and the correct host instance.
- **Dropouts or echo.** Start with wired/internal speakers and a reliable LAN. Disable duplicate monitoring such as “Listen to this device” on the cable return and tune delay again.
- **Recovery.** Run Stop.cmd. If the old speaker was unplugged, choose an available physical output manually. Inspect routing.log and startup.log inside the install folder.
- **Upgrade or remove.** Stop the split, close the mixer and use Quit Tray. Rerun the installer to upgrade; it preserves device names and EQ. To uninstall, restore the saved Sunshine settings, restart Sunshine and remove the install directory and the SplitDesk desktop/startup shortcuts. Remove drivers separately only when no other application needs them.
- **Optional login startup.** Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\install.ps1 -StartAtLogin` in the extracted kit. This starts the native tray helper at login; open the mixer on demand.

## Native build and source run

For desktop and tray use, run `Install.cmd` after building. It installs CPython’s GUI launcher into the environment so opening the mixer does not start a console window.

The distribution includes x64 binaries for the tray launcher and six-section stereo filter. From the repository root, using Zig 0.14.1 on x64 Windows:

```powershell
zig cc -Os -s -shared mixer/filters.c -o mixer/tone.dll
zig cc -Os -s -municode '-Wl,--subsystem,windows' mixer/tray.c -lshell32 -luser32 -o mixer/SplitDeskTray.exe
uv venv --python 3.14 venv
uv pip install --python venv/Scripts/python.exe -r requirements.txt
venv/Scripts/python.exe launch.py
```

Run `venv/Scripts/python.exe tools/make_demo.py` to regenerate the stereo WAV. The installer can also be tested in an empty directory with `-InstallDir`, `-NoShortcuts` and `-NoLaunch`. Configuration and recovery files are local to that installation. Use a single active routing installation per Windows user.
