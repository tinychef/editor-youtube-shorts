"""CLI: python -m shorts <comando> …   (ver README o `python -m shorts -h`)"""
import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m shorts", description="Editor de YouTube Shorts")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="revisa dependencias (ffmpeg, Python, Chromium, modelos)")

    p = sub.add_parser("prepare", help="transcribe, corta pausas/muletillas y recorta a la persona")
    p.add_argument("video")
    p.add_argument("--work", default="work", help="carpeta de trabajo (default: work/)")
    p.add_argument("--name", help="nombre del proyecto (default: nombre del archivo)")
    p.add_argument("--lang", default="es", help="idioma (es, en, …; vacío = detectar)")
    p.add_argument("--model", default=None, help="modelo Whisper (default: large-v3-turbo; rápido: small)")
    p.add_argument("--vocab", default="", help="nombres propios extra para Whisper, separados por comas")
    p.add_argument("--drop", default="", help="palabras a quitar por índice de transcript_src.txt: '12-30,45-47'")
    p.add_argument("--pause", type=float, default=0.20, help="pausa máxima que se conserva (s)")
    p.add_argument("--keep-fillers", action="store_true", help="no quitar «eh», «mmm»…")
    p.add_argument("--fast", action="store_true", help="recorte rápido (modelo simple; más fugas del fondo)")
    p.add_argument("--fps", type=float, default=30)
    p.add_argument("--recut", action="store_true", help="reutiliza la transcripción y solo rehace cortes")

    r = sub.add_parser("render", help="renderiza un plan.json → MP4 1080x1920")
    r.add_argument("plan")
    r.add_argument("--out", help="ruta del MP4 (default: la del plan o out/<nombre>.mp4)")
    r.add_argument("--draft", action="store_true", help="borrador rápido: 540x960, sin refinado")
    r.add_argument("--from", dest="t_from", type=float, default=None, help="renderiza solo desde este segundo")
    r.add_argument("--to", dest="t_to", type=float, default=None, help="… hasta este segundo")
    r.add_argument("--frames", default=None, help="solo cuadros sueltos para revisar: '1.5,8,12.25' → PNG")
    r.add_argument("--jobs", type=int, default=0, help="procesos en paralelo (default: núcleos)")

    q = sub.add_parser("qa", help="hoja de contactos + loudness de un MP4 para revisarlo")
    q.add_argument("video")
    q.add_argument("--every", type=float, default=2.0)

    lg = sub.add_parser("logo", help="busca un logo y lo guarda como PNG para revisarlo")
    lg.add_argument("names", nargs="+")

    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        from .doctor import doctor
        sys.exit(doctor())
    if a.cmd == "prepare":
        from .prepare import prepare
        from .transcribe import DEFAULT_MODEL
        prepare(a.video, work=a.work, name=a.name, language=a.lang or None, model=a.model or DEFAULT_MODEL,
                vocab=a.vocab, drop=a.drop, max_pause=a.pause, fillers=not a.keep_fillers,
                quality="fast" if a.fast else "hq", fps=a.fps, recut=a.recut)
    elif a.cmd == "render":
        from .render import render
        render(a.plan, out=a.out, draft=a.draft, t_from=a.t_from, t_to=a.t_to, frames=a.frames, jobs=a.jobs)
    elif a.cmd == "qa":
        from .qa import qa
        qa(a.video, every=a.every)
    elif a.cmd == "logo":
        from .logos import preview
        preview(a.names)


if __name__ == "__main__":
    main()
