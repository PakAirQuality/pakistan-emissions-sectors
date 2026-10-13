#!/usr/bin/env python3
"""Review sheets for the figure redesign: colour-vision simulations, and before beside after.

    python3 paper_national/figures/redesign/make_review_sheets.py [--before DIR]

For each of the eight figures this writes simulations/<stem>.png: the figure as drawn, in
greyscale, and under simulated deuteranopia, protanopia and tritanopia. With --before, the
directory holding the seven superseded figure PDFs, it also writes before_after/<stem>.png with
the old and new figure rendered at one resolution, so a millimetre on one is a millimetre on
the other.

The simulation is Machado, Oliveira and Fernandes (2009) at full severity, applied in linear
RGB. It is a screening aid: it shows whether two colours that carry different meanings collapse
into one, which is the question, and it is not a certificate of accessibility.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FIGURES = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(FIGURES))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.report import manuscript_style as S  # noqa: E402

plt = S.use()
DPI = 110

MACHADO = {
    "Deuteranopia": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413],
                     [-0.011820, 0.042940, 0.968881]],
    "Protanopia": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216],
                   [-0.003882, -0.048116, 1.051998]],
    "Tritanopia": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602],
                   [0.004733, 0.691367, 0.303900]],
}
# which old file each new figure replaces; figure 6 was the lower half of the old evidence plate
BEFORE = {"f01_construction": "fig1_data_products", "f02_inventory": "fig2_inventory",
          "f03_evidence_uncertainty": "fig3_evidence_uncertainty", "f04_gas_maps": "fig_ghg_grid",
          "f05_spatial_evidence": "fig_ghg_grid_evidence",
          "f06_proxy_concentration": "fig_ghg_grid_evidence",
          "f07_btr_ratios": "fig4_validation", "f08_managed_soils": "fig5_managed_soils"}


def render(pdf):
    with tempfile.TemporaryDirectory() as tmp:
        stem = os.path.join(tmp, "page")
        subprocess.run(["pdftoppm", "-r", str(DPI), "-png", "-singlefile", pdf, stem], check=True)
        return plt.imread(stem + ".png")[..., :3].astype("float64")


def to_linear(rgb):
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def to_srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)


def simulate(rgb, matrix):
    return to_srgb(to_linear(rgb) @ np.asarray(matrix).T)


def grey(rgb):
    lum = to_linear(rgb) @ np.array([0.2126, 0.7152, 0.0722])
    return np.repeat(to_srgb(lum)[..., None], 3, axis=2)


def sheet(images, titles, path, ncols):
    nrows = int(np.ceil(len(images) / ncols))
    height = max(im.shape[0] / im.shape[1] for im in images)
    fig = plt.figure(figsize=(7.0 * ncols, (7.0 * height + 0.35) * nrows))
    for i, (im, title) in enumerate(zip(images, titles)):
        ax = fig.add_subplot(nrows, ncols, i + 1)
        ax.imshow(im, interpolation="lanczos")
        ax.set_title(title, loc="left", fontsize=11)
        ax.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.01, wspace=0.03, hspace=0.10)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=80, metadata={"Software": None})
    plt.close(fig)


def main(argv):
    before = argv[argv.index("--before") + 1] if "--before" in argv else None
    for stem in S.FIGURES:
        new = render(os.path.join(FIGURES, stem + ".pdf"))
        views = [new, grey(new)] + [simulate(new, m) for m in MACHADO.values()]
        sheet(views, ["As drawn", "Greyscale"] + list(MACHADO), os.path.join(HERE, "simulations", stem + ".png"), 2)
        if before:
            old = render(os.path.join(before, BEFORE[stem] + ".pdf"))
            # one resolution for both, padded to one canvas: physical size is preserved
            h, w = max(old.shape[0], new.shape[0]), max(old.shape[1], new.shape[1])
            pad = lambda im: np.pad(im, ((0, h - im.shape[0]), (0, w - im.shape[1]), (0, 0)), constant_values=1.0)
            sheet([pad(old), pad(new)], ["Before: %s.pdf (as drawn; LaTeX then rescaled it)" % BEFORE[stem],
                                         "After: %s.pdf (placed at this size in both layouts)" % stem],
                  os.path.join(HERE, "before_after", stem + ".png"), 2)
        print("reviewed %s" % stem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
