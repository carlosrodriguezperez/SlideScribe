**System Prompt / Product Requirements Document (PRD)**
**Project Name:** `SlideScribe-CLI`
**Project Type:** Cross-Platform Command Line Interface (CLI) Tool (Python)

### 1. Objective

Build a lightweight, zero-UI Python CLI tool that takes a single local lecture slide `.pdf` as an argument. The tool must rasterize the slides, use a Multimodal Vision LLM to extract text/salvage math formulas into LaTeX, synthesize comprehensive text explanations for content-sparse slides, and compile an editable `.md` file alongside an asset folder *directly inside the same parent directory where the source PDF lives*.

---

### 2. Core Philosophy & Strict Constraints

* **Zero-UI Policy:** No Flask, FastAPI, Streamlit, or web frontends. Interaction is purely terminal-based or triggered by OS integration handlers.
* **Target OS Compatibility:** Must support **Linux** and **Windows** (Native CMD/PowerShell). macOS support is explicitly out of scope.
* **Relative Path Immortality:** The output Markdown file and its slide asset folder must sit side-by-side in the source directory. Image links inside the Markdown must use localized relative paths so that moving the folder to Google Drive, Obsidian, or another machine never breaks the visual links.

---

### 3. Execution & Directory Behavior

When the tool is called via terminal:
`slidescribe /path/to/my_lectures/Lec_04_Calculus.pdf`

The script must resolve the environment and execute inside the PDF's parent folder:

```text
/path/to/my_lectures/          <-- The folder containing the user's PDF
│
├── Lec_04_Calculus.pdf        # Unmodified Source PDF
│
├── Lec_04_Calculus.md         # Generated Master Notes Document
│
└── Lec_04_Calculus_slides/    # Generated Asset Directory
    ├── slide_1.png
    ├── slide_2.png
    └── slide_X.png

```

---

### 4. Step-by-Step Architecture Pipeline

1. **Path Resolution:** Use Python's `pathlib` to dynamically capture the absolute path of the target PDF passed as an argument. Extract the parent directory and file stem (filename without extension).
2. **Rasterization:** Render the PDF pages into `.png` images using `pdf2image`. Save them natively into `{parent_dir}/{pdf_stem}_slides/slide_{page_num}.png`.
3. **Structured API Synthesis:** Iterate through the images and pass them to the Vision LLM (Preferred: Google Gemini 1.5 Flash via `google-genai` SDK for massive context handling). Enforce structured JSON output via Pydantic using this schema:
```python
from pydantic import BaseModel

class SlideParsed(BaseModel):
    slide_number: int
    slide_title: str
    transcribed_content: str  # All raw text and blurry equations converted to clean markdown/LaTeX ($...$ or $$...$$)
    synthesized_explanation: str # A 1-2 paragraph textbook-style explanation of the concepts or diagrams shown on the slide

```


4. **Markdown Generation:** Compile the structured data objects into a cohesive, sequential `.md` document placed right next to the original PDF.

---

### 5. Markdown Output Structural Specification

The generated Markdown file must strictly match this structural layout for every slide to provide inline visual verification:

```markdown
# Lecture Notes: [PDF Stem Name]

***

## Slide 1: [Extracted Slide Title]

![Slide 1 View](./[PDF_Stem]_slides/slide_1.png)

### Slide Contents
* [Bullet point text...]
* Matrix equation recovered from image:
  $$\mathbf{A}\mathbf{x} = \lambda\mathbf{x}$$

---
**🤖 AI Synthesized Explanation:**
*This slide establishes the core theorem of... If the professor skipped explaining this visual matrix grid, it represents the transformation where vectors only scale, never change direction...*

***

```

---

### 6. Development Phasing Protocol (For the Agent)

Do not write the whole script at once. Please proceed sequentially:

* **Phase 1:** Provide the setup configuration files (`pyproject.toml` or `setup.py`) that establish `slidescribe` as a globally recognized terminal command on Windows and Linux using Python entry points. Provide a minimal "Hello World" CLI script to test this global routing.
* **Phase 2:** Implement the local `pdf2image` extraction chunk. Include a check for the system dependency `poppler` and display helpful CLI installation tips if it is missing on the user's OS.
* **Phase 3:** Integrate the structured Vision LLM calls, Pydantic validation, and the markdown compiler loop.

