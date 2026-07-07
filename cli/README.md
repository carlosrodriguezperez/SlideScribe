# SlideScribe-CLI

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Powered by Gemini](https://img.shields.io/badge/Powered%20by-Gemini-orange.svg)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**SlideScribe-CLI** is a lightweight, zero-UI command-line tool that transforms lecture slide PDFs into highly structured, clean Markdown notes. Powered by Gemini Multimodal Vision models, it transcribes text, salvages blurry or hand-written mathematical formulas into pristine LaTeX, synthesizes textbook-style explanations for sparse slides, and embeds relative-pathed slide images side-by-side.

---

## 🌟 Key Features

* **Zero-UI Philosophy:** Pure terminal-based execution. Perfect for automation, scripting, and piping.
* **Global Context-Aware Chunking:** Loads and transmits all slide images in every request to provide Gemini with complete lecture context, while chunking the output generation (in batches of 15 slides) to safely stay within Gemini's 8,192 output token limit.
* **OCR & LaTeX Salvaging:** Automatically recovers blurry slide math equations and represents them in standard LaTeX formatting (both inline `$ ... $` and block `$$ ... $$`).
* **Rigorous Technical Explanations:** Generates highly technical, detailed, and mathematically rigorous explanations for each slide to synthesize core academic concepts, even if the slides themselves are visually sparse.
* **CLI & Language Flexibility:** Customize both the explanation and transcription languages dynamically, change models, or disable explanations entirely.
* **Resilient Network Architecture:** Automatically retries API calls (up to 3 times with exponential backoff) to handle transient internet or API connectivity issues seamlessly.
* **Relative Path Immortality:** Built entirely with `pathlib`. Slide assets and Markdown notes sit side-by-side using forward slashes, ensuring they stay perfectly linked on GitHub, Google Drive, Obsidian, or other devices.

---

## 🛠️ Installation & Setup

### 1. Prerequisites (Poppler)

`SlideScribe-CLI` relies on `poppler` for rendering PDF slides into images.

* **Linux (Debian/Ubuntu):**
  ```bash
  sudo apt-get update
  sudo apt-get install poppler-utils
  ```

> [!NOTE]
> `SlideScribe-CLI` is designed primarily for Linux. Windows users can run it via WSL or by using the legacy `support/windows` branch.

### 2. Install the Package

To run `slidescribe` globally from any terminal, it is highly recommended to install it using [`pipx`](https://pipx.pypa.io/). This isolates the tool's dependencies while exposing the command system-wide.

```bash
git clone https://github.com/carlosrodriguezperez/SlideScribe-CLI.git
cd SlideScribe-CLI
pipx install -e .
```

> [!NOTE]
> If you don't have `pipx` installed, you can install it via `pip install pipx` and then run `pipx ensurepath`. If you prefer a local project installation, you can use `pip install -e .` instead, but you will need to activate the virtual environment each time.

### 3. API Key Configuration

You can configure your Gemini API key globally using one of two professional methods:

#### Option A: Environment Variable (Recommended)

**For Linux/macOS:**
Export the variable directly in your shell configuration file (e.g., `~/.bashrc` or `~/.zshrc`):
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

#### Option B: Configuration File
Create a `.env` configuration file. SlideScribe-CLI will look for it in the following locations:
1. The current working directory (`./.env`)
2. Your home directory (`~/.slidescribe.env`)
3. Your standard config directory (`~/.config/slidescribe/.env`)

Insert your key into the file like this:
```env
GEMINI_API_KEY="your_gemini_api_key_here"
```

---

## 🚀 Usage

Execute `slidescribe` on local PDF files, image files (`.png`, `.jpg`, `.jpeg`, `.webp`), or directories:

```bash
# Convert a single PDF file (default behavior)
slidescribe /path/to/my_lectures/Lec_05_Machine_Learning.pdf

# Convert a single image file
slidescribe slide_screenshot.png

# Convert a folder containing screenshots/images or PDFs
slidescribe /path/to/folder_of_slides/

# Merge and compile multiple PDFs and images together into one Markdown file
slidescribe Lec_05_Part1.pdf Lec_05_Part2.pdf Lec_05_Appendix.png -o Lec_05_Combined
```

### CLI Command Options

| Argument | Description | Default |
| :--- | :--- | :--- |
| `targets` | Path to the source PDF file(s), image file(s), or directories containing them. | *Required* (one or more) |
| `--model` | Dynamic Gemini model selection (e.g. `gemini-2.5-pro` or `gemini-2.5-flash`). | `gemini-2.5-flash` |
| `--no-explanations` | Skips generating AI explanations, extracting text & LaTeX equations extremely fast. | `False` |
| `--no-contents` | Skips writing the transcribed slide contents to the markdown output. | `False` |
| `-el`, `--explanation-language` | The language in which to generate the AI explanations (alias: `-l`, `--language`). | `English` |
| `-tl`, `--transcription-language` | The language in which to transcribe the slide contents (alias: `-t`). | `English` |
| `-eo`, `--extract-only` | Only extract PDF pages as images and exit without calling the model. | `False` |
| `-o`, `--output` | Custom destination name or path for the compiled Markdown and slides folder. | `None` |
| `-dd`, `--detect-diagrams` | Detect, crop, and embed diagrams and charts from slides. | `False` |
| `--version` | Prints the version number (`0.2.0`) and exits. | N/A |
| `-h`, `--help` | Show help menu. | N/A |

#### Examples

**Run with high-quality explanations using Pro:**
```bash
slidescribe Lec_05_Machine_Learning.pdf --model gemini-2.5-pro
```

**Run with explanations generated in Spanish:**
```bash
slidescribe Lec_05_Machine_Learning.pdf --explanation-language Spanish
```

**Run ultra-fast transcription (no explanations, saves tokens/cost):**
```bash
slidescribe Lec_05_Machine_Learning.pdf --no-explanations
```

---

## 📸 The Showcase

In the showcase folder there are two examples of the power of `SlideScribe-CLI`:

### 1. Generating Explanations in a Specific Language

Here we process `BadSlides_LackingExplanations.pdf`, which lacks explanations on the slides. We request the AI to synthesize the missing explanations in Galician, and we use `--no-contents` to skip printing the minimal slide text:

```bash
slidescribe showcase/BadSlides_LackingExplanations.pdf --explanation-language Galician --no-contents
```

### 2. Writing complex math formulas

Here we process `BadSlides_LatexInImages.pdf` (using default settings). This slides contain plenty of math symbols. We turn them into beautiful LaTeX formulas.

```bash
slidescribe showcase/BadSlides_LatexInImages.pdf
```

---

## 👨‍💻 Author

**Carlos Rodríguez Pérez**  
- GitHub: [@carlosrodriguezperez](https://github.com/carlosrodriguezperez)