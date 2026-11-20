"""Edita el video de demostración: acelera las esperas del LLM y exporta MP4 (H.264) para YouTube.

    docker run --rm -v "$PWD:/w" -w /w --entrypoint python3 linuxserver/ffmpeg:version-7.1-cli scripts/video_editar.py
    (o con ffmpeg instalado: python3 scripts/video_editar.py)

Lee docs/video/crudo.webm y docs/video/tramos.json; escribe docs/video/demo_chatbot_unab.mp4.
"""
import json
import subprocess
from pathlib import Path

D = Path("docs/video")
SPEED = 12.0   # las esperas del LLM se ven 12 veces más rápido

info = json.loads((D / "tramos.json").read_text(encoding="utf-8"))
total = float(info["total"])
fast = sorted((max(0.0, a), min(total, b)) for a, b in info["fast"] if b - a > 1.5)

# Tramos alternos: normal → acelerado → normal ...
segs, t = [], 0.0
for a, b in fast:
    if a > t:
        segs.append((t, a, 1.0))
    segs.append((a, b, SPEED))
    t = b
if t < total:
    segs.append((t, total, 1.0))

parts = []
for i, (a, b, sp) in enumerate(segs):
    parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{sp},fps=30[v{i}]")
graph = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[out]"

cmd = ["ffmpeg", "-y", "-i", str(D / "crudo.webm"), "-filter_complex", graph, "-map", "[out]",
       "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
       str(D / "demo_chatbot_unab.mp4")]
subprocess.run(cmd, check=True)
dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                      str(D / "demo_chatbot_unab.mp4")], capture_output=True, text=True).stdout.strip()
print(f"listo: {D / 'demo_chatbot_unab.mp4'} ({float(dur):.0f} s; crudo {total:.0f} s, {len(fast)} esperas aceleradas x{SPEED:g})")
