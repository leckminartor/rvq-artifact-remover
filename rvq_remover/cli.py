"""CLI batch processor: python -m rvq_remover.cli input.(wav|mp3|flac) [output.wav]"""

import argparse
import os
import sys

from .engine import load_audio, process, save_audio


def main():
    ap = argparse.ArgumentParser(description="Remove RVQ artifacts from audio.")
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--strength", type=float, default=0.6, help="0..1")
    ap.add_argument("--hf-start", type=float, default=4000.0)
    ap.add_argument("--comb-freq", type=float, default=75.0)
    ap.add_argument("--no-comb", action="store_true")
    ap.add_argument("--no-unfreeze", action="store_true")
    ap.add_argument("--no-transient", action="store_true")
    ap.add_argument("--no-bandlimit", action="store_true")
    ap.add_argument("--neural", action="store_true",
                    help="AI neural stage (Demucs separation + per-stem cleanup)")
    ap.add_argument("--model", default="htdemucs", choices=["htdemucs", "htdemucs_ft"])
    args = ap.parse_args()

    out = args.output or os.path.splitext(args.input)[0] + "_derq.wav"
    y, sr = load_audio(args.input)
    y_out, rep = process(
        y, sr, strength=args.strength, hf_start=args.hf_start,
        comb_freq=args.comb_freq,
        use_comb=not args.no_comb, use_unfreeze=not args.no_unfreeze,
        use_transient=not args.no_transient, use_bandlimit=not args.no_bandlimit,
    )
    if args.neural:
        from . import neural
        y_out = neural.neural_enhance(
            y_out, sr, strength=args.strength, hf_start=args.hf_start,
            comb_freq=args.comb_freq, model_name=args.model,
            status_cb=lambda m: print(f"  [neural] {m}"),
        )
    save_audio(out, y_out, sr)
    b = rep["before"]
    print(f"Saved: {out}")
    print(f"Pipeline: {'DSP + neural (' + args.model + ')' if args.neural else 'DSP stages'}")
    print(f"Frozen bins: {b['frozen_band_pct']*100:.1f}%")
    print(f"Comb depth:  {b['comb_score']:.3f} @ {args.comb_freq} Hz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
