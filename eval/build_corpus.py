import argparse
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "corpus" / "manifest.json"

FONT_PATHS = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/tahoma.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
)


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def arabic_font(font_path: Path | None = None) -> str:
    path = font_path or next((path for path in FONT_PATHS if path.is_file()), None)
    if path is None or not path.is_file():
        raise FileNotFoundError(
            "An Arabic TTF font is required. Pass --font with a local Arabic font path."
        )
    if "EvalArabic" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("EvalArabic", str(path)))
    return "EvalArabic"


def build_corpus(output: Path, *, font_path: Path | None = None) -> list[Path]:
    manifest = load_manifest()
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported corpus manifest schema")

    font = arabic_font(font_path) if any(
        doc["language"] == "ar" for doc in manifest["documents"]
    ) else "Helvetica"
    output.mkdir(parents=True, exist_ok=True)
    produced: list[Path] = []

    for doc in manifest["documents"]:
        path = output / doc["filename"]
        pdf = Canvas(str(path), pagesize=A4, invariant=1, pageCompression=1)
        pdf.setTitle(doc["title"])
        face = font if doc["language"] == "ar" else "Helvetica"

        for expected, page in enumerate(doc["pages"], start=1):
            if page["number"] != expected:
                raise ValueError(f"Non-sequential pages in {doc['id']}")

            pdf.setFont(face, 15)
            pdf.drawString(40, 782, doc["title"])
            pdf.setFont(face, 11)
            pdf.drawString(40, 750, f"Page {expected}")
            for index, sentence in enumerate(page["lines"]):
                if len(sentence) > 170:
                    raise ValueError("Evaluation line is too long")
                pdf.setFont(face, 12)
                pdf.drawString(40, 686 - index * 95, sentence)
            pdf.showPage()

        pdf.save()
        produced.append(path)

    return produced


def main() -> None:
    parser = argparse.ArgumentParser(description="Build open DocuAsk evaluation PDFs")
    parser.add_argument("--output", type=Path, default=ROOT / "corpus" / "pdfs")
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    for path in build_corpus(args.output, font_path=args.font):
        print(path)


if __name__ == "__main__":
    main()
