"""TTS clients for Manim Edu Harness (urllib only, no SDK).

Default provider: Volcengine Doubao TTS 2.0 (seed-tts-2.0).
Optional fallback: Zhipu GLM-TTS via TTS_PROVIDER=zhipu.

Volcengine docs:
  https://docs.volcengine.com/docs/6561/1598757
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import uuid
import wave
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request


class TTSError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Volcengine Doubao TTS 2.0 (HTTP unidirectional chunked)
# ---------------------------------------------------------------------------

_VOLC_DEFAULT_SPEAKER = "zh_male_m191_uranus_bigtts"  # 云舟 — 教学向男声 2.0


class VolcengineTTS:
    """豆包语音合成模型 2.0 via openspeech v3 unidirectional HTTP."""

    def __init__(
        self,
        *,
        app_id: str | None = None,
        access_token: str | None = None,
        secret_key: str | None = None,
        resource_id: str | None = None,
        speaker: str | None = None,
        max_chars: int = 900,
    ) -> None:
        self.app_id = (app_id or os.environ.get("VOLC_TTS_APP_ID") or "").strip()
        self.access_token = (
            access_token or os.environ.get("VOLC_TTS_ACCESS_TOKEN") or ""
        ).strip()
        # Stored for future signed APIs; v3 TTS uses Access Token as X-Api-Access-Key.
        self.secret_key = (secret_key or os.environ.get("VOLC_TTS_SECRET_KEY") or "").strip()
        self.resource_id = (
            resource_id
            or os.environ.get("VOLC_TTS_RESOURCE_ID")
            or "seed-tts-2.0"
        ).strip()
        self.speaker = (
            speaker or os.environ.get("VOLC_TTS_SPEAKER") or _VOLC_DEFAULT_SPEAKER
        ).strip()
        self.endpoint = (
            os.environ.get("VOLC_TTS_ENDPOINT")
            or "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
        ).strip()
        self.max_chars = max_chars
        if not self.app_id or not self.access_token:
            raise TTSError(
                "VOLC_TTS_APP_ID / VOLC_TTS_ACCESS_TOKEN not set. "
                "Add them to .env (never commit secrets)."
            )

    def synthesize(self, text: str, output_path: str | Path) -> bool:
        cleaned = _prepare_narration(text)
        if not cleaned:
            return False
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        chunks = _chunk_text(cleaned, self.max_chars)
        audio_blobs: list[bytes] = []
        for chunk in chunks:
            audio_blobs.append(self._request_speech(chunk))
        raw = b"".join(audio_blobs)
        if not raw:
            raise TTSError("Volcengine TTS returned empty audio")
        _write_audio_bytes(raw, out)
        return out.is_file() and out.stat().st_size > 44

    def _request_speech(self, text: str) -> bytes:
        body = {
            "user": {"uid": f"manim-edu-{uuid.uuid4().hex[:12]}"},
            "req_params": {
                "text": text,
                "speaker": self.speaker,
                "audio_params": {
                    "format": os.environ.get("VOLC_TTS_FORMAT", "mp3"),
                    "sample_rate": int(os.environ.get("VOLC_TTS_SAMPLE_RATE", "24000")),
                },
            },
        }
        speed = os.environ.get("VOLC_TTS_SPEED")
        if speed:
            body["req_params"]["speed_ratio"] = float(speed)

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib_request.Request(
            self.endpoint,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Api-App-Id": self.app_id,
                "X-Api-Access-Key": self.access_token,
                "X-Api-Resource-Id": self.resource_id,
            },
        )
        try:
            with urllib_request.urlopen(req, timeout=180) as resp:
                payload = resp.read()
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TTSError(f"Volcengine TTS HTTP {exc.code}: {detail[:800]}") from None
        except urllib_error.URLError as exc:
            raise TTSError(f"Volcengine TTS network error: {exc.reason}") from None

        return _parse_volc_audio_payload(payload)


def _parse_volc_audio_payload(payload: bytes) -> bytes:
    """Parse v3 chunked/NDJSON responses into raw audio bytes."""
    text = payload.decode("utf-8", errors="replace").strip()
    if not text:
        raise TTSError("Volcengine TTS empty body")

    # Single JSON object (some gateways buffer the whole stream).
    if text.startswith("{") and "\n" not in text:
        try:
            obj = json.loads(text)
            return _audio_from_volc_obj(obj, allow_end=True)
        except json.JSONDecodeError:
            pass

    audio = bytearray()
    # NDJSON / concatenated JSON lines
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        code = obj.get("code")
        if code in (0, "0") and obj.get("data"):
            audio.extend(base64.b64decode(obj["data"]))
        elif code in (20000000, "20000000"):
            # success end marker
            continue
        elif code not in (0, "0", None) and code not in (20000000, "20000000"):
            msg = obj.get("message") or obj
            raise TTSError(f"Volcengine TTS error code={code}: {msg}")

    if audio:
        return bytes(audio)

    # Fallback: try to find any "data":"..." base64 fields via regex
    parts = re.findall(r'"data"\s*:\s*"([A-Za-z0-9+/=]+)"', text)
    if parts:
        return b"".join(base64.b64decode(p) for p in parts)

    raise TTSError(f"Volcengine TTS: could not parse audio from response ({text[:200]!r})")


def _audio_from_volc_obj(obj: dict[str, Any], *, allow_end: bool) -> bytes:
    code = obj.get("code")
    if code in (20000000, "20000000") and allow_end and not obj.get("data"):
        raise TTSError("Volcengine TTS finished with no audio data")
    if code not in (0, "0", None) and code not in (20000000, "20000000"):
        raise TTSError(f"Volcengine TTS error code={code}: {obj.get('message')}")
    data = obj.get("data")
    if not data:
        raise TTSError(f"Volcengine TTS missing data field: {obj!r}"[:400])
    if isinstance(data, str):
        return base64.b64decode(data)
    raise TTSError("Volcengine TTS data field is not base64 string")


# ---------------------------------------------------------------------------
# Optional Zhipu fallback
# ---------------------------------------------------------------------------


class ZhipuTTS:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        voice: str | None = None,
        max_chars: int = 1000,
    ) -> None:
        self.api_key = (api_key or os.environ.get("ZHIPU_API_KEY") or "").strip()
        self.base_url = (
            os.environ.get("ZHIPU_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4"
        ).rstrip("/")
        self.model = os.environ.get("ZHIPU_TTS_MODEL") or "glm-tts"
        aliases = {"zhichu": "tongtong", "aisong": "xiaochen", "male": "tongtong", "female": "xiaochen"}
        raw = voice or os.environ.get("ZHIPU_TTS_VOICE") or "tongtong"
        self.voice = aliases.get(raw.lower(), raw)
        self.max_chars = max_chars
        if not self.api_key:
            raise TTSError("ZHIPU_API_KEY is not set")

    def synthesize(self, text: str, output_path: str | Path) -> bool:
        cleaned = _prepare_narration(text)
        if not cleaned:
            return False
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        chunks = _chunk_text(cleaned, self.max_chars)
        blobs = [self._request_speech(c) for c in chunks]
        raw = b"".join(blobs)
        _write_audio_bytes(raw, out)
        return out.is_file() and out.stat().st_size > 44

    def _request_speech(self, text: str) -> bytes:
        body = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": "wav",
            "speed": float(os.environ.get("ZHIPU_TTS_SPEED", "1.0")),
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib_request.Request(
            f"{self.base_url}/audio/speech",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib_request.urlopen(req, timeout=180) as resp:
                payload = resp.read()
                ctype = (resp.headers.get("Content-Type") or "").lower()
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TTSError(f"Zhipu TTS HTTP {exc.code}: {detail[:800]}") from None
        except urllib_error.URLError as exc:
            raise TTSError(f"Zhipu TTS network error: {exc.reason}") from None
        if "application/json" in ctype:
            raise TTSError(f"Zhipu TTS JSON error: {payload[:800]!r}")
        if not payload:
            raise TTSError("Zhipu TTS empty body")
        return payload


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _prepare_narration(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if s.startswith("```"):
            continue
        if s.startswith("#"):
            s = s.lstrip("#").strip()
        lines.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _chunk_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts = re.split(r"(?<=[。！？；!?;\n])", text)
    chunks: list[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        if len(buf) + len(part) <= max_chars:
            buf += part
            continue
        if buf.strip():
            chunks.append(buf.strip())
        if len(part) <= max_chars:
            buf = part
        else:
            for i in range(0, len(part), max_chars):
                piece = part[i : i + max_chars].strip()
                if piece:
                    chunks.append(piece)
            buf = ""
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def _write_audio_bytes(raw: bytes, out: Path) -> None:
    """Write provider bytes; convert mp3→wav when needed for Manim."""
    if raw[:4] == b"RIFF" or out.suffix.lower() != ".wav":
        out.write_bytes(raw)
        return
    # Likely mp3/pcm — prefer ffmpeg → wav
    with tempfile.TemporaryDirectory(prefix="tts_conv_") as tmp:
        src = Path(tmp) / "in.bin"
        # sniff
        if raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb" or raw[:2] == b"\xff\xf3":
            src = Path(tmp) / "in.mp3"
        else:
            src = Path(tmp) / "in.mp3"  # volc default format is mp3
        src.write_bytes(raw)
        if _which("ffmpeg"):
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(src),
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and out.is_file():
                return
        # fallback: keep mp3 bytes but rename? Manim wants path — write .mp3 sibling
        mp3_out = out.with_suffix(".mp3")
        mp3_out.write_bytes(raw)
        # Also copy as wav path if conversion failed — leave mp3 for add_sound fallback
        out.write_bytes(raw)


def _which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def _make_client():
    provider = (os.environ.get("TTS_PROVIDER") or "volcengine").strip().lower()
    if provider in {"volc", "volcengine", "doubao", "bytedance", "huoshan"}:
        return VolcengineTTS()
    if provider in {"zhipu", "glm"}:
        return ZhipuTTS()
    # Auto: prefer Volc if configured
    if os.environ.get("VOLC_TTS_APP_ID") and os.environ.get("VOLC_TTS_ACCESS_TOKEN"):
        return VolcengineTTS()
    if os.environ.get("ZHIPU_API_KEY"):
        return ZhipuTTS()
    raise TTSError("No TTS credentials: set VOLC_TTS_* or ZHIPU_API_KEY")


def synthesize_narration_file(
    narration_md: Path,
    output_wav: Path,
    *,
    api_key: str | None = None,
) -> tuple[bool, str]:
    """Harness helper: narration.md → narration.wav. Never raises to caller."""
    if not narration_md.is_file():
        return False, f"missing {narration_md.name}"
    text = narration_md.read_text(encoding="utf-8").strip()
    if not text:
        return False, "narration.md is empty"
    try:
        # api_key retained for Zhipu backward-compat; Volc uses env.
        if api_key and (os.environ.get("TTS_PROVIDER") or "").lower() in {"zhipu", "glm"}:
            client: Any = ZhipuTTS(api_key=api_key)
        else:
            client = _make_client()
        ok = client.synthesize(text, output_wav)
        # Prefer wav; if only mp3 sibling exists, point note
        if ok and output_wav.is_file():
            return True, f"wrote {output_wav.name} ({output_wav.stat().st_size} bytes)"
        mp3 = output_wav.with_suffix(".mp3")
        if mp3.is_file():
            return True, f"wrote {mp3.name} ({mp3.stat().st_size} bytes); convert to wav if needed"
        return False, "synthesize returned False"
    except TTSError as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"unexpected TTS error: {exc}"


# Back-compat aliases
ZhipuTTSError = TTSError

__all__ = [
    "VolcengineTTS",
    "ZhipuTTS",
    "TTSError",
    "ZhipuTTSError",
    "synthesize_narration_file",
]
