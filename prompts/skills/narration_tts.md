# Skill: narration_tts

## 旁白文件

Writer 必须产出口语旁白（落盘 `narration.md`）：约 200–450 字，200–300 字/分钟；少念生硬 LaTeX。

## 场景强制挂载

`construct` **末尾**必须保留：

```python
self.load_and_play_narration()
self.pad_to_narration_length()
```

`load_and_play_narration`：

1. 读 `narration.wav`
2. 临时 `renderer.skip_animations = False`
3. `add_sound(..., time_offset=-self.time)` 钉到 t=0

禁止删除或改名该函数。Harness 用豆包 TTS（seed-tts-2.0）从 narration.md 合成 wav。

{{snippet:speech-guidelines}}

<!-- learned:safe-narration-helpers -->
<!-- count=1 updated=2026-07-31T02:00Z -->
## Learned from traces: keep canonical narration helpers

- Never `open("narration.wav","rb")` + `add_sound(bytes)` — Path TypeError.
- Never `self.renderer.file_writer.movie_file_writer` in `pad_to_narration_length`.
- Use rule_gate canonical: `wave.open` for duration + `add_sound(audio_file, time_offset=...)`.
<!-- /learned:safe-narration-helpers -->

