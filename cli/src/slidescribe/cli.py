import argparse
import sys
import os
import re
import time
import json
import dotenv
from pathlib import Path
import pdf2image
from pdf2image.exceptions import PDFInfoNotInstalledError
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from PIL import Image, ImageFilter, ImageStat

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

class DiagramBoundingBox(BaseModel):
    ymin: int = Field(description="Normalized y-coordinate of the top edge of the diagram (0 to 1000).")
    xmin: int = Field(description="Normalized x-coordinate of the left edge of the diagram (0 to 1000).")
    ymax: int = Field(description="Normalized y-coordinate of the bottom edge of the diagram (0 to 1000).")
    xmax: int = Field(description="Normalized x-coordinate of the right edge of the diagram (0 to 1000).")
    label: str = Field(description="A short label/description of the diagram (e.g. 'flowchart', 'architecture diagram', 'data graph').")

class SlideParsed(BaseModel):
    page_number: int = Field(
        description="The 1-based index of this slide in the provided list of images (e.g. 1 for the first image, 2 for the second, etc.)."
    )
    slide_number: int = Field(
        description="The actual slide number printed on the slide itself, if visible. If not visible, use page_number."
    )
    slide_title: str
    transcribed_content: str
    synthesized_explanation: str
    diagrams: list[DiagramBoundingBox] = Field(
        description="A list of diagrams, graphs, charts, or illustrations found on this slide. If no diagrams are present, return an empty list."
    )

class SlideDeck(BaseModel):
    slides: list[SlideParsed]

def analyze_slides(
    image_paths: list[Path], 
    start_slide: int, 
    end_slide: int, 
    model_name: str, 
    no_explanations: bool,
    detect_diagrams: bool,
    language: str = "English",
    transcription_language: str = "English",
    client: genai.Client = None,
    uploaded_files: list = None,
    global_context_limit: int = None
) -> list[SlideParsed]:
    if client is None:
        client = genai.Client()
    print(f"Analyzing slides {start_slide} to {end_slide} using {model_name}...")
    
    contents = []
    num_images = len(image_paths)
    
    # Determine the slice of slides to pass as context
    if global_context_limit is not None:
        start_idx = max(1, start_slide - global_context_limit)
        end_idx = min(num_images, end_slide + global_context_limit)
    else:
        start_idx = 1
        end_idx = num_images

    for i in range(start_idx, end_idx + 1):
        contents.append(f"Image {i}:")
        if uploaded_files:
            contents.append(uploaded_files[i - 1])
        else:
            contents.append(Image.open(image_paths[i - 1]))
        
    explanation_instruction = (
        f"provide a 1-2 paragraph highly technical, detailed, and mathematically rigorous (where applicable) explanation of the concepts shown in {language}. Focus on the underlying theory, formal definitions, and mechanisms."
        if not no_explanations else
        "since explanations are disabled, do not write explanations and set the synthesized_explanation field to an empty string."
    )
    
    diagram_system_instruction = ""
    if detect_diagrams:
        diagram_system_instruction = (
            "\n   - **Diagram Placeholders**: If you identify any diagrams, charts, graphs, or illustrations on a slide, you MUST "
            "insert a placeholder `[DIAGRAM_{index}]` (e.g. `[DIAGRAM_0]` for the first diagram in the diagrams list, `[DIAGRAM_1]` for the second, etc.) "
            "at the exact position in the `transcribed_content` text where that diagram is located in the flow of the slide content."
        )
    system_instruction = (
        "Analyze the slide images provided and transcribe their contents accurately into clean, well-formatted Markdown and LaTeX, adhering to these guidelines:\n"
        f"   - **Language**: All text, titles, and headers in the `transcribed_content` and `slide_title` fields must be written in {transcription_language}. If the original text on the slides is in a different language, translate it into {transcription_language} while maintaining the exact meaning.\n"
        "   - **Structure**: Organize the transcribed content using Markdown lists (bulleted `-` or numbered `1.`), bolding, and headers (`####`) to faithfully represent the slide's original hierarchy and layout. Do not output raw, flat blocks of text.\n"
        "   - **Paragraphs**: Separate distinct ideas, bullet points, or sections with double newlines (using empty lines between them) to prevent the Markdown renderer from collapsing them into a single line.\n"
        "   - **Inline Math**: Use inline LaTeX (`$...$`) for individual variables, small expressions, and symbols (e.g., `$x$`, `$\\mu$`). Do not add spaces around the inner delimiters (e.g., write `$x$` instead of `$ x $`).\n"
        "   - **Block Math**: Use block LaTeX (`$$...$$`) on their own lines for complex, multiline, or prominent equations. Ensure there is an empty line before and after the block math so it renders correctly.\n"
        "   - **Underscores & Formatting**: Ensure underscores (`_`) used for subscripts (e.g., `$x_{t}$` or `$\\mu_{A}$`) are always enclosed within math delimiters to avoid conflicts with Markdown italicization.\n"
        "   - **No Meta/Descriptions**: Do not include physical descriptions of images, diagrams, or UI elements (like \"[Image of...]\") in the transcription unless they contain readable text or formulas. Exclude header/footer noise (e.g. copyright notices, slide numbers) if they do not contribute to the educational content."
        f"{diagram_system_instruction}"
    )

    diagram_prompt_instruction = (
        "Additionally, for each slide, analyze and identify all diagrams, graphs, charts, or drawings. "
        "Locate their bounding boxes normalized from 0 to 1000 in the format [ymin, xmin, ymax, xmax].\n"
        "CRITICAL BOUNDING BOX RULES:\n"
        "1. Be extremely generous with the bounding box boundaries so no part of the diagram is cropped.\n"
        "2. Do NOT include textual mathematical equations, text paragraphs, or standalone formulas in the bounding box of a diagram. "
        "The bounding box must strictly enclose only the graphical drawings, charts, or illustrations (and any labels embedded directly inside them). "
        "For example, if a slide has a flowchart/drawing on one side and math equations on another, the bounding box must only cover the flowchart/drawing.\n"
        "3. Ignore decorative slide background templates, themes, watermarks, or background patterns (such as background curves, waves, or diagonal lines). The bounding box must only focus on the actual foreground diagram content.\n\n"
        "Add the diagrams to the `diagrams` list field with a short, descriptive label. For each diagram you add, "
        "make sure to insert its placeholder (e.g., `[DIAGRAM_0]`) in the `transcribed_content` text."
        if detect_diagrams else
        "Since diagram detection is disabled, do not detect diagrams and set the `diagrams` list field to an empty list."
    )
    prompt = (
        f"You are given all the slides of the presentation for global context to understand the structure of the lecture.\n"
        f"Please analyze the images labeled 'Image {start_slide}' to 'Image {end_slide}' (inclusive, based on the labels provided above).\n\n"
        f"For each of these specified slides: set the `page_number` field in the response schema to the number corresponding to its label "
        f"(e.g., for 'Image 3', set `page_number` to 3), extract the title, transcribe all text and mathematical formulas accurately "
        f"into the transcribed_content field following the system guidelines, and {explanation_instruction} "
        f"{diagram_prompt_instruction}"
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
                    system_instruction=system_instruction,
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
        else:
            print("Hint: Install poppler for your OS.", file=sys.stderr)
        sys.exit(1)
    except Exception:
        pass

def optimize_and_save_image(img: Image.Image, out_file: Path):
    """
    Optimizes and saves the PIL Image as a PNG.
    Calculates edge density to adaptively resize low-complexity slides (title/ending slides)
    to a max dimension of 1000px, and high-complexity slides (text/diagrams) to a max dimension of 1600px.
    Enables PNG saving optimization.
    """
    try:
        edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
        edge_mean = ImageStat.Stat(edges).mean[0]
    except Exception as e:
        print(f"Warning: Complexity analysis failed: {e}. Defaulting to high complexity.", file=sys.stderr)
        edge_mean = 99.0

    if edge_mean < 5.0:
        max_dim = 1000
    else:
        max_dim = 1600

    width, height = img.size
    if width > max_dim or height > max_dim:
        if width > height:
            new_width = max_dim
            new_height = int(height * (max_dim / width))
        else:
            new_height = max_dim
            new_width = int(width * (max_dim / height))

        resample_filter = getattr(Image, "Resampling", None)
        filter_type = resample_filter.LANCZOS if resample_filter else getattr(Image, "LANCZOS", Image.BICUBIC)
        img = img.resize((new_width, new_height), filter_type)

    img.save(out_file, "PNG", optimize=True)

def extract_slides(pdf_path: Path, output_dir: Path, dpi: int = 150):
    pdf_path = pdf_path.resolve()
    if not pdf_path.exists() or not pdf_path.is_file():
        print(f"Error: Target file '{pdf_path}' does not exist or is not a file.", file=sys.stderr)
        sys.exit(1)
    
    if output_dir.exists() and output_dir.is_dir():
        existing_images = list(output_dir.glob("slide_*.png"))
        if existing_images:
            print(f"Directory '{output_dir.name}' already exists with {len(existing_images)} slides. Skipping PDF extraction.")
            return len(existing_images)

    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Rasterizing '{pdf_path.name}'...")
    try:
        images = pdf2image.convert_from_path(str(pdf_path), dpi=dpi)
    except Exception as e:
        print(f"Error during PDF extraction: {e}", file=sys.stderr)
        sys.exit(1)
        
    for i, image in enumerate(images, start=1):
        out_file = output_dir / f"slide_{i}.png"
        optimize_and_save_image(image, out_file)
        
    print(f"Successfully saved {len(images)} slides to '{output_dir}'.")
    return len(images)

def collect_and_extract_slides(targets: list[Path], output_dir: Path, dpi: int = 150) -> int:
    if output_dir.exists() and output_dir.is_dir():
        existing_images = list(output_dir.glob("slide_*.png"))
        if existing_images:
            print(f"Directory '{output_dir.name}' already exists with {len(existing_images)} slides. Skipping slide extraction.")
            return len(existing_images)
            
    output_dir.mkdir(parents=True, exist_ok=True)
    
    slide_count = 0
    
    def process_file(file_path: Path):
        nonlocal slide_count
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            print(f"Rasterizing PDF '{file_path.name}'...")
            try:
                images = pdf2image.convert_from_path(str(file_path), dpi=dpi)
                for image in images:
                    slide_count += 1
                    out_file = output_dir / f"slide_{slide_count}.png"
                    optimize_and_save_image(image, out_file)
            except Exception as e:
                print(f"Error during PDF extraction for '{file_path.name}': {e}", file=sys.stderr)
        elif suffix in [".png", ".jpg", ".jpeg", ".webp"]:
            print(f"Copying image '{file_path.name}'...")
            try:
                slide_count += 1
                out_file = output_dir / f"slide_{slide_count}.png"
                with Image.open(file_path) as img:
                    optimize_and_save_image(img, out_file)
            except Exception as e:
                print(f"Error processing image '{file_path.name}': {e}", file=sys.stderr)

    for target in targets:
        target = target.resolve()
        if not target.exists():
            print(f"Warning: Target '{target}' does not exist. Skipping.", file=sys.stderr)
            continue
            
        if target.is_file():
            process_file(target)
        elif target.is_dir():
            print(f"Scanning directory '{target.name}'...")
            files = sorted(list(target.iterdir()))
            for f in files:
                if f.is_file():
                    process_file(f)
                    
    print(f"Successfully saved {slide_count} slides to '{output_dir}'.")
    return slide_count

def compile_markdown(output_md: Path, output_dir: Path, model_name: str, no_explanations: bool, detect_diagrams: bool, language: str = "English", transcription_language: str = "English", no_contents: bool = False, force: bool = False, no_files_api: bool = False, global_context_limit: int = None):
    print(f"Compiling Markdown to '{output_md.name}'...")
    
    # Collect all image paths dynamically from the slides directory
    image_paths = []
    if output_dir.exists() and output_dir.is_dir():
        for p in output_dir.glob("slide_*.png"):
            match = re.match(r"^slide_(\d+)\.png$", p.name)
            if match:
                image_paths.append((int(match.group(1)), p))
        image_paths.sort()
        image_paths = [p for _, p in image_paths]
            
    if not image_paths:
        print("No slide images found to process.", file=sys.stderr)
        return

    cache_path = output_dir / ".slidescribe_cache.json"
    
    # Handle force flag: delete existing cache if it exists
    if force:
        if cache_path.exists():
            try:
                cache_path.unlink()
                print("Force flag specified. Existing cache file deleted.")
            except Exception as e:
                print(f"Warning: Failed to delete cache file under force flag: {e}", file=sys.stderr)
        loaded_slides = []
    else:
        loaded_slides = []
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                
                cached_meta = cache_data.get("metadata", {})
                meta_matches = (
                    cached_meta.get("model") == model_name and
                    cached_meta.get("no_explanations") == no_explanations and
                    cached_meta.get("detect_diagrams") == detect_diagrams and
                    cached_meta.get("language") == language and
                    cached_meta.get("transcription_language") == transcription_language
                )
                
                if meta_matches:
                    raw_slides = cache_data.get("slides", [])
                    loaded_slides = [SlideParsed(**s) for s in raw_slides]
                    print(f"Loaded {len(loaded_slides)} parsed slides from cache.")
                else:
                    print("Cache configuration mismatch. Invalidation of previous cache. Starting fresh.")
                    try:
                        cache_path.unlink()
                    except Exception as e:
                        print(f"Warning: Failed to delete mismatching cache file: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Could not read cache file ({e}). Starting fresh.")
                try:
                    if cache_path.exists():
                        cache_path.unlink()
                except Exception:
                    pass

    all_parsed_slides = loaded_slides.copy()
    cached_pages = {s.page_number for s in all_parsed_slides}
    chunk_size = 15
    num_images = len(image_paths)
    
    # Determine which chunks actually need processing
    chunks_to_process = []
    for chunk_start in range(1, num_images + 1, chunk_size):
        chunk_end = min(chunk_start + chunk_size - 1, num_images)
        chunk_pages = set(range(chunk_start, chunk_end + 1))
        if not chunk_pages.issubset(cached_pages):
            chunks_to_process.append((chunk_start, chunk_end))

    # Initialize client and upload files if we have chunks to process
    client = genai.Client()
    uploaded_files = []
    if chunks_to_process and not no_files_api:
        try:
            for i, path in enumerate(image_paths, start=1):
                print(f"Uploading slide {i}/{num_images} to Gemini Files API...")
                uploaded = client.files.upload(file=path)
                uploaded_files.append(uploaded)
        except Exception as e:
            print(f"Warning: Failed to upload slides to Gemini Files API: {e}. Falling back to direct payload upload.", file=sys.stderr)
            # Cleanup any already uploaded files
            for f in uploaded_files:
                try:
                    client.files.delete(name=f.name)
                except Exception:
                    pass
            uploaded_files = []

    try:
        for chunk_start, chunk_end in chunks_to_process:
            try:
                parsed_chunk = analyze_slides(
                    image_paths,
                    chunk_start,
                    chunk_end,
                    model_name,
                    no_explanations,
                    detect_diagrams,
                    language,
                    transcription_language,
                    client=client,
                    uploaded_files=uploaded_files,
                    global_context_limit=global_context_limit
                )
                
                # Map slides by page to prevent duplicates and keep sorted order
                slides_by_page = {s.page_number: s for s in all_parsed_slides}
                for s in parsed_chunk:
                    slides_by_page[s.page_number] = s
                all_parsed_slides = list(slides_by_page.values())
                
                # Save updated cache
                cache_data = {
                    "metadata": {
                        "model": model_name,
                        "no_explanations": no_explanations,
                        "detect_diagrams": detect_diagrams,
                        "language": language,
                        "transcription_language": transcription_language,
                    },
                    "slides": [slide.model_dump() for slide in all_parsed_slides]
                }
                try:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(cache_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"Warning: Failed to write cache file: {e}", file=sys.stderr)
                    
            except Exception as e:
                print(f"Error during batch API request for slides {chunk_start}-{chunk_end}: {e}", file=sys.stderr)
                return

        # Sort parsed slides by page_number just in case they are out of order
        all_parsed_slides.sort(key=lambda s: s.page_number)

        with open(output_md, "w", encoding="utf-8") as f:
            f.write(f"# Lecture Notes: {output_md.stem}\n\n***\n\n")
            
            for parsed in all_parsed_slides:
                idx = parsed.page_number
                if 1 <= idx <= len(image_paths):
                    slide_file_path = image_paths[idx - 1]
                    slide_file_name = slide_file_path.name
                else:
                    slide_file_path = None
                    slide_file_name = f"slide_{parsed.slide_number}.png"
                
                f.write(f"## Slide {parsed.slide_number}: {parsed.slide_title}\n\n")
                
                if not no_explanations:
                    f.write(f"**🤖 AI Synthesized Explanation:**\n*{parsed.synthesized_explanation}*\n\n")
                    
                unplaced_diagrams = []
                if detect_diagrams and parsed.diagrams and slide_file_path and slide_file_path.exists():
                    try:
                        with Image.open(slide_file_path) as img:
                            width, height = img.size
                            for k, diag in enumerate(parsed.diagrams):
                                # Add a 3% padding (safety margin) to handle minor model coordinate inaccuracies
                                x_pad = int(width * 0.03)
                                y_pad = int(height * 0.03)
                                
                                left = max(0, int(diag.xmin * width / 1000) - x_pad)
                                top = max(0, int(diag.ymin * height / 1000) - y_pad)
                                right = min(width, int(diag.xmax * width / 1000) + x_pad)
                                bottom = min(height, int(diag.ymax * height / 1000) + y_pad)
                                
                                if right > left and bottom > top:
                                    cropped = img.crop((left, top, right, bottom))
                                    crop_name = f"slide_{idx}_diagram_{k+1}.png"
                                    crop_path = output_dir / crop_name
                                    cropped.save(crop_path, "PNG")
                                    
                                    md_img_link = f"![{diag.label}](./{output_dir.name}/{crop_name})"
                                    placeholder = rf"\[DIAGRAM_{k}\]"
                                    new_content, count = re.subn(placeholder, md_img_link, parsed.transcribed_content)
                                    if count > 0:
                                        parsed.transcribed_content = new_content
                                    else:
                                        unplaced_diagrams.append(md_img_link)
                    except Exception as e:
                        print(f"Warning: Failed to crop diagrams on slide {idx}: {e}", file=sys.stderr)
                
                if not no_contents:
                    f.write(f"### Slide Contents\n{parsed.transcribed_content}\n\n")
                    if unplaced_diagrams:
                        f.write("#### Slide Diagrams\n")
                        for link in unplaced_diagrams:
                            f.write(f"{link}\n\n")
                    
                f.write(f"![Slide {parsed.slide_number} View](./{output_dir.name}/{slide_file_name})\n\n")
                f.write("***\n\n")
                
        # Delete cache file on successful compilation
        if cache_path.exists():
            try:
                cache_path.unlink()
            except Exception as e:
                print(f"Warning: Failed to delete cache file upon completion: {e}", file=sys.stderr)

        print(f"Successfully compiled {len(all_parsed_slides)} slides into '{output_md.name}'.")

    finally:
        if uploaded_files:
            print("Cleaning up remote slide files from Gemini Files API...")
            for f in uploaded_files:
                try:
                    client.files.delete(name=f.name)
                except Exception as e:
                    print(f"Warning: Failed to delete remote file {f.name} from Files API: {e}", file=sys.stderr)

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
        "--explanation-language",
        "--language",
        "-el",
        "-l",
        dest="language",
        type=str,
        default="English",
        help="The language in which to generate the AI explanations (default: English)."
    )
    parser.add_argument(
        "--transcription-language",
        "-tl",
        "-t",
        dest="transcription_language",
        type=str,
        default="English",
        help="The language in which to transcribe the slide contents (default: English)."
    )
    parser.add_argument(
        "--extract-only",
        "-eo",
        action="store_true",
        help="Only extract PDF pages as images and exit without calling the model."
    )
    parser.add_argument(
        "--detect-diagrams",
        "-dd",
        action="store_true",
        help="Detect, crop, and embed diagrams and charts from slides."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Custom destination name or path for the compiled Markdown and slides folder."
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force regeneration of all slides, ignoring and deleting any existing cache."
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="DPI to use when rasterizing PDF slides (default: 150)."
    )
    parser.add_argument(
        "--no-files-api",
        action="store_true",
        help="Disable using the Gemini Files API and upload files in the request payload instead."
    )
    parser.add_argument(
        "--global-context-limit",
        type=int,
        default=None,
        help="Limit the global context window to N slides before and after the chunk (default: pass all slides)."
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help="Path to the source PDF file(s), image file(s), or directories containing them."
    )

    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)
    
    if args.targets:
        targets = [Path(t) for t in args.targets]
        load_env()
        check_poppler()
        
        # Calculate output paths
        first_target = targets[0].resolve()
        if args.output:
            out_base = Path(args.output)
            if out_base.suffix.lower() == ".md":
                out_base = out_base.with_suffix("")
            output_md = out_base.with_suffix(".md")
            output_dir = out_base.parent / f"{out_base.name}_slides"
        else:
            if len(targets) == 1:
                if first_target.is_dir():
                    output_dir = first_target.parent / f"{first_target.name}_slides"
                    output_md = first_target.parent / f"{first_target.name}.md"
                else:
                    output_md = first_target.with_suffix(".md")
                    output_dir = first_target.parent / f"{first_target.stem}_slides"
            else:
                output_md = first_target.parent / f"{first_target.stem}_merged.md"
                output_dir = first_target.parent / f"{first_target.stem}_merged_slides"
            
        num_slides = collect_and_extract_slides(targets, output_dir, dpi=args.dpi)
        if args.extract_only:
            sys.exit(0)
        compile_markdown(output_md, output_dir, args.model, args.no_explanations, args.detect_diagrams, args.language, args.transcription_language, args.no_contents, args.force, no_files_api=args.no_files_api, global_context_limit=args.global_context_limit)
        sys.exit(0)
    
    parser.print_help()

if __name__ == "__main__":
    main()
