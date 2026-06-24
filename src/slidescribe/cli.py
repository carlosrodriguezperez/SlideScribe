import argparse
import sys
from pathlib import Path
import pdf2image
from pdf2image.exceptions import PDFInfoNotInstalledError
from slidescribe import __version__

def check_poppler():
    try:
        # Passing an invalid path to check if pdfinfo is accessible
        pdf2image.pdfinfo_from_path("")
    except PDFInfoNotInstalledError:
        print("Error: 'poppler' is not installed or not in PATH.", file=sys.stderr)
        if sys.platform.startswith("linux"):
            print("Hint: Install it via 'sudo apt-get install poppler-utils'", file=sys.stderr)
        elif sys.platform == "win32":
            print("Hint: Install it via 'choco install poppler' or download binaries and add to PATH.", file=sys.stderr)
        else:
            print("Hint: Install poppler for your OS.", file=sys.stderr)
        sys.exit(1)
    except Exception:
        pass

def extract_slides(pdf_path: Path):
    pdf_path = pdf_path.resolve()
    if not pdf_path.exists() or not pdf_path.is_file():
        print(f"Error: Target file '{pdf_path}' does not exist or is not a file.", file=sys.stderr)
        sys.exit(1)
    
    output_dir = pdf_path.parent / f"{pdf_path.stem}_slides"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Rasterizing '{pdf_path.name}'...")
    try:
        images = pdf2image.convert_from_path(str(pdf_path))
    except Exception as e:
        print(f"Error during PDF extraction: {e}", file=sys.stderr)
        sys.exit(1)
        
    for i, image in enumerate(images, start=1):
        out_file = output_dir / f"slide_{i}.png"
        image.save(out_file, "PNG")
        
    print(f"Successfully saved {len(images)} slides to '{output_dir}'.")

def main():
    parser = argparse.ArgumentParser(description="SlideScribe CLI - Convert Lecture PDFs to Markdown")
    parser.add_argument(
        "--version", 
        action="store_true", 
        help="Print the version number and exit."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Path to the source PDF file."
    )

    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)
    
    if args.target:
        target_path = Path(args.target)
        check_poppler()
        extract_slides(target_path)
        sys.exit(0)
    
    parser.print_help()

if __name__ == "__main__":
    main()
