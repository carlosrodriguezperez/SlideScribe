import argparse
import sys
import os
from pathlib import Path
import pdf2image
from pdf2image.exceptions import PDFInfoNotInstalledError
from pydantic import BaseModel
from google import genai
from google.genai import types
from PIL import Image

from slidescribe import __version__

def load_env():
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

class SlideParsed(BaseModel):
    slide_number: int
    slide_title: str
    transcribed_content: str
    synthesized_explanation: str

def analyze_slide(image_path: Path, slide_number: int) -> SlideParsed:
    client = genai.Client()
    print(f"Uploading and analyzing {image_path.name} with Gemini...")
    
    img = Image.open(image_path)
    prompt = (
        f"You are analyzing slide {slide_number}. "
        "Extract the title, and transcribe all text and mathematical formulas accurately into clean Markdown/LaTeX. "
        "Provide a 1-2 paragraph textbook-style explanation of the concepts shown on the slide."
    )
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SlideParsed,
            temperature=0.2,
        ),
    )
    
    return response.parsed

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
        load_env()
        check_poppler()
        extract_slides(target_path)
        
        # Checkpoint 3 test: Analyze only the first slide
        output_dir = target_path.parent / f"{target_path.stem}_slides"
        slide_1 = output_dir / "slide_1.png"
        
        if slide_1.exists():
            print("\n--- Checkpoint 3 Test: Analyzing Slide 1 ---")
            parsed = analyze_slide(slide_1, 1)
            print("\n=== STRUCTURED JSON OUTPUT ===")
            print(parsed.model_dump_json(indent=2))
        else:
            print("Error: slide_1.png not found for testing.")
        
        sys.exit(0)
    
    parser.print_help()

if __name__ == "__main__":
    main()
