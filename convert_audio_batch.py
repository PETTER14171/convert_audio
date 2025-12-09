#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
convert_audio_batch.py (v3)
Convierte audios en lote a múltiples formatos usando FFmpeg.

Ejemplos rápidos:

# WAV PCM 16-bit, mono, 8 kHz (telefonía)
python convert_audio_batch.py -i "./audios" -o "./convertidos" -f wav -r 8000 -c 1 --overwrite

# Igual que arriba, pero con atajo:
python convert_audio_batch.py -i "./audios" -o "./convertidos" -f wav --telephony --overwrite

# Si FFmpeg no está en PATH:
python convert_audio_batch.py -i "./audios" -f wav -r 8000 -c 1 --overwrite --ffmpeg "C:/ffmpeg/bin/ffmpeg.exe"
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_INPUTS = {
    ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".wma", ".aiff", ".aif", ".opus", ".caf"
}

def resolve_ffmpeg(ffmpeg_arg: str | None) -> str:
    """
    Devuelve la ruta al ejecutable de ffmpeg.
    Prioriza --ffmpeg; si no, busca en PATH.
    Lanza SystemExit con mensaje claro si no se encuentra.
    """
    if ffmpeg_arg:
        p = Path(ffmpeg_arg).expanduser()
        if p.is_file():
            return str(p)
        cand = p / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if cand.is_file():
            return str(cand)
        sys.exit(f"[ERROR] No se encontró FFmpeg en --ffmpeg: {ffmpeg_arg}")

    found = shutil.which("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if found:
        return found

    msg = [
        "[ERROR] No se encontró 'ffmpeg' en el sistema.",
        "Soluciones:",
        "  • Instálalo y agrega a PATH, o",
        "  • Usa la opción --ffmpeg con la ruta completa al ejecutable.",
        "",
        "Windows (rápido):",
        "  winget install Gyan.FFmpeg   (o)   choco install ffmpeg",
        "  O descarga: https://www.gyan.dev/ffmpeg/builds/ y apunta --ffmpeg a ffmpeg.exe",
        "macOS:       brew install ffmpeg",
        "Ubuntu/Debian: sudo apt-get install ffmpeg",
    ]
    sys.exit("\n".join(msg))

def check_ffmpeg_available(ffmpeg_bin: str):
    """Verifica que FFmpeg se pueda ejecutar."""
    try:
        subprocess.run([ffmpeg_bin, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except FileNotFoundError:
        sys.exit(f"[ERROR] No se puede ejecutar FFmpeg en: {ffmpeg_bin}")
    except subprocess.CalledProcessError:
        sys.exit(f"[ERROR] FFmpeg parece estar corrupto o no es ejecutable: {ffmpeg_bin}")

def build_ffmpeg_cmd(ffmpeg_bin: str, src: Path, dst: Path, args: argparse.Namespace) -> list[str]:
    cmd = [
        ffmpeg_bin, "-hide_banner", "-loglevel", "error",
        "-y" if args.overwrite else "-n",
        "-i", str(src),
    ]

    # Filtros de audio (solo normalización si se pidió)
    afilters = []
    if args.normalize:
        # Normalización EBU R128 (one-pass)
        afilters.append("loudnorm=I=-16:LRA=11:TP=-1.5:linear=true")

    if afilters:
        cmd += ["-af", ",".join(afilters)]

    # Códec según extensión destino
    ext = dst.suffix.lower()
    if ext == ".mp3":
        cmd += ["-c:a", "libmp3lame"]
        if args.bitrate: cmd += ["-b:a", args.bitrate]
    elif ext in (".aac", ".m4a"):
        cmd += ["-c:a", "aac"]
        if args.bitrate: cmd += ["-b:a", args.bitrate]
    elif ext == ".opus":
        cmd += ["-c:a", "libopus"]
        if args.bitrate: cmd += ["-b:a", args.bitrate]
    elif ext == ".ogg":
        cmd += ["-c:a", "libvorbis"]
        if args.bitrate: cmd += ["-b:a", args.bitrate]
    elif ext == ".flac":
        cmd += ["-c:a", "flac"]
    elif ext in (".wav", ".aiff", ".aif"):
        # PCM 16-bit little-endian (WAV estándar)
        cmd += ["-c:a", "pcm_s16le"]
    else:
        # fallback genérico
        if args.bitrate: cmd += ["-b:a", args.bitrate]

    # Sample rate y canales (sin filtros problemáticos)
    if args.samplerate: cmd += ["-ar", str(args.samplerate)]
    if args.channels:   cmd += ["-ac", str(args.channels)]

    cmd += [str(dst)]
    return cmd

def main():
    parser = argparse.ArgumentParser(description="Convierte audios en lote con FFmpeg.")
    parser.add_argument("--input", "-i", required=True, help="Carpeta de entrada (recursivo).")
    parser.add_argument("--output", "-o", default="./convertidos", help="Carpeta de salida.")
    parser.add_argument("--formats", "-f", required=True,
                        help="Formatos separados por coma (ej: mp3,wav,flac,ogg,opus,aac,m4a)")
    parser.add_argument("--bitrate", "-b", default=None, help="Bitrate (ej: 128k, 192k, 256k).")
    parser.add_argument("--samplerate", "-r", type=int, default=None, help="Frecuencia de muestreo (ej: 44100, 48000, 8000).")
    parser.add_argument("--channels", "-c", type=int, choices=[1, 2], default=None, help="Canales (1=mono, 2=stereo).")
    parser.add_argument("--normalize", action="store_true", help="Normaliza volumen (loudnorm EBU R128).")
    parser.add_argument("--overwrite", action="store_true", help="Reemplazar si ya existe el archivo destino.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra los comandos sin ejecutar FFmpeg.")
    parser.add_argument("--ffmpeg", default=None, help="Ruta al ejecutable de FFmpeg (ej: C:/ffmpeg/bin/ffmpeg.exe).")
    parser.add_argument("--telephony", action="store_true",
                        help="Atajo para audio de telefonía: WAV PCM 16-bit, 8 kHz, mono (equivale a -f wav -r 8000 -c 1).")

    args = parser.parse_args()

    ffmpeg_bin = resolve_ffmpeg(args.ffmpeg)
    check_ffmpeg_available(ffmpeg_bin)

    in_dir = Path(args.input).expanduser().resolve()
    out_dir = Path(args.output).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Procesa lista de formatos
    targets = [f".{fmt.strip().lower().lstrip('.')}" for fmt in args.formats.split(",") if fmt.strip()]
    if not targets:
        print("Error: especifica al menos un formato en --formats")
        return

    # Atajo de telefonía: si no se dieron r/c, los fijamos
    if args.telephony:
        if ".wav" not in targets:
            print("[Aviso] --telephony está pensado para .wav; continúo, pero considera incluir 'wav' en --formats.")
        if args.samplerate is None:
            args.samplerate = 8000
        if args.channels is None:
            args.channels = 1

    # Buscar archivos de audio recursivamente
    audio_files = [p for p in in_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_INPUTS]
    if not audio_files:
        print("No se encontraron archivos de audio en:", in_dir)
        return

    total_jobs = 0
    for src in audio_files:
        rel = src.relative_to(in_dir)
        for ext in targets:
            dst = out_dir / ext.lstrip(".") / rel.with_suffix(ext)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() and not args.overwrite:
                continue
            total_jobs += 1

    print(f"Archivos encontrados: {len(audio_files)}")
    print(f"Tareas a ejecutar:    {total_jobs}")
    if total_jobs == 0:
        print("Nada por hacer (posiblemente todo ya convertido).")
        return

    done = 0
    for src in audio_files:
        rel = src.relative_to(in_dir)
        for ext in targets:
            dst = out_dir / ext.lstrip(".") / rel.with_suffix(ext)
            if dst.exists() and not args.overwrite:
                continue

            cmd = build_ffmpeg_cmd(ffmpeg_bin, src, dst, args)

            print(f"[{done+1}/{total_jobs}] {src.name} -> {dst.suffix[1:].upper()}  ({dst})")
            if args.dry_run:
                print("  CMD:", " ".join(cmd))
            else:
                try:
                    result = subprocess.run(
                        cmd,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                except subprocess.CalledProcessError as e:
                    print("  Error al convertir:", src, "->", dst)
                    if e.stderr:
                        print("  FFmpeg dice:\n", e.stderr.strip())
                    else:
                        print("  (FFmpeg no devolvió detalles)")
                except Exception as e:
                    print("  Error inesperado:", src, "->", dst, "|", repr(e))
            done += 1

    print("Proceso finalizado.")

if __name__ == "__main__":
    main()
