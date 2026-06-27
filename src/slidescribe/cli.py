import argparse
import sys
import os
import time
import dotenv
from pathlib import Path
import pdf2image
from pdf2image.exceptions import PDFInfoNotInstalledError
from pydantic import BaseModel
from google import genai
from google.genai import types
from PIL import Image

from slidescribe import __version__

def load_env():
    env_paths = [
        Path(".env"),
        Path.home() / ".slidescribe.env",
        Path.home() / ".config" / "slidescribe" / ".env"
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            dotenv.load_dotenv(env_path)

class SlideParsed(BaseModel):
    slide_number: int
    slide_title: str
    transcribed_content: str
    synthesized_explanation: str

class SlideDeck(BaseModel):
    slides: list[SlideParsed]

def analyze_slides(
    image_paths: list[Path], 
    start_slide: int, 
    end_slide: int, 
    model_name: str, 
    no_explanations: bool,
    language: str = "English"
) -> list[SlideParsed]:
    client = genai.Client()
    print(f"Analyzing slides {start_slide} to {end_slide} using {model_name}...")
    
    contents = []
    for path in image_paths:
        contents.append(Image.open(path))
        
    explanation_instruction = (
        f"provide a 1-2 paragraph textbook-style explanation of the concepts shown in {language}."
        if not no_explanations else
        "since explanations are disabled, do not write explanations and set the synthesized_explanation field to an empty string."
    )
    
    prompt = (
        f"You are given all the slides of the presentation for global context to understand the structure of the lecture. "
        f"Please analyze slides {start_slide} to {end_slide} (inclusive, 1-indexed based on their order in the list). "
        f"For each of these specified slides: extract the title, transcribe all text and mathematical formulas accurately "
        f"into clean Markdown/LaTeX ($...$ or $$...$$), and {explanation_instruction}"
    )
    contents.append(prompt)
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SlideDeck,
                    temperature=0.2,
                ),
            )
            
            if response.parsed is None:
                raise ValueError(
                    f"Failed to parse structured JSON response from Gemini. "
                    f"Raw output: {response.text}"
                )
                
            return response.parsed.slides
        except Exception as e:
            if attempt == max_retries:
                raise e
            print(f"Warning: API call failed on attempt {attempt}/{max_retries}: {e}. Retrying in 5 seconds...", file=sys.stderr)
            time.sleep(5)

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
    
    if output_dir.exists() and output_dir.is_dir():
        existing_images = list(output_dir.glob("slide_*.png"))
        if existing_images:
            print(f"Directory '{output_dir.name}' already exists with {len(existing_images)} slides. Skipping PDF extraction.")
            return len(existing_images)

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
    return len(images)

def compile_markdown(pdf_path: Path, num_slides: int, model_name: str, no_explanations: bool, language: str = "English", no_contents: bool = False):
    output_md = pdf_path.with_suffix(".md")
    output_dir_name = f"{pdf_path.stem}_slides"
    
    print(f"Compiling Markdown to '{output_md.name}'...")
    
    # Collect all image paths
    image_paths = []
    for i in range(1, num_slides + 1):
        slide_file = pdf_path.parent / output_dir_name / f"slide_{i}.png"
        if slide_file.exists():
            image_paths.append(slide_file)
            
    if not image_paths:
        print("No slide images found to process.", file=sys.stderr)
        return

    all_parsed_slides = []
    chunk_size = 15
    for chunk_start in range(1, num_slides + 1, chunk_size):
        chunk_end = min(chunk_start + chunk_size - 1, num_slides)
        try:
            parsed_chunk = analyze_slides(image_paths, chunk_start, chunk_end, model_name, no_explanations, language)
            all_parsed_slides.extend(parsed_chunk)
        except Exception as e:
            print(f"Error during batch API request for slides {chunk_start}-{chunk_end}: {e}", file=sys.stderr)
            return

    # Sort parsed slides by slide_number just in case they are out of order
    all_parsed_slides.sort(key=lambda s: s.slide_number)

    with open(output_md, "w", encoding="utf-8") as f:
        f.write(f"# Lecture Notes: {pdf_path.stem}\n\n***\n\n")
        
        for parsed in all_parsed_slides:
            i = parsed.slide_number
            slide_file_name = f"slide_{i}.png"
            
            f.write(f"## Slide {i}: {parsed.slide_title}\n\n")
            
            if not no_explanations:
                f.write(f"**🤖 AI Synthesized Explanation:**\n*{parsed.synthesized_explanation}*\n\n")
                
            if not no_contents:
                f.write(f"### Slide Contents\n{parsed.transcribed_content}\n\n")
                
            f.write(f"![Slide {i} View](./{output_dir_name}/{slide_file_name})\n\n")
            f.write("***\n\n")
            
    print(f"Successfully compiled {len(all_parsed_slides)} slides into '{output_md.name}'.")

def main():
    parser = argparse.ArgumentParser(description="SlideScribe CLI - Convert Lecture PDFs to Markdown")
    parser.add_argument(
        "--version", 
        action="store_true", 
        help="Print the version number and exit."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model to use for analysis (default: gemini-2.5-flash)."
    )
    parser.add_argument(
        "--no-explanations",
        action="store_true",
        help="Skip generating detailed textbook-style explanations for slides."
    )
    parser.add_argument(
        "--no-contents",
        action="store_true",
        help="Skip writing the transcribed slide contents to the markdown file."
    )
    parser.add_argument(
        "--language",
        "-l",
        type=str,
        default="English",
        help="The language in which to generate the AI explanations (default: English)."
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
        num_slides = extract_slides(target_path)
        compile_markdown(target_path, num_slides, args.model, args.no_explanations, args.language, args.no_contents)
        sys.exit(0)
    
    parser.print_help()

if __name__ == "__main__":
    main()
