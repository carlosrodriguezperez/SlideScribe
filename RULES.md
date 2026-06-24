# ENGINEERING STANDARDS & REPOSITORY PROTOCOL

**Target:** AI Coding Agent (`@PRD.md` contains the functional spec)

You are not just writing a working script; you are packaging an **open-source developer tool intended for a public portfolio showcase**. Every line of code, file placement, and configuration you generate must pass a Senior Open-Source Maintainer's code review.

Adhere strictly to the following 5 Delivery Directives:

### 1. Modern Packaging Standard (`pyproject.toml`)

Do **not** use legacy `setup.py` or `setup.cfg`. The project must be packaged using a modern `pyproject.toml` file.

The user must be able to navigate to the root of this repository, run:

```bash
pip install -e .

```

...and instantly have the global terminal command `slidescribe` mapped to the entry point of our CLI.

### 2. Mandatory Repository Hygiene

Before you write any application logic, your very first action must be generating a production-grade `.gitignore` tailored for Python. It **must** explicitly ignore:

* `__pycache__/` and `.pytest_cache/`
* `*.egg-info/` and `dist/` or `build/`
* Virtual environment folders (`.venv/`, `venv/`, `env/`)
* `.env` files (CRITICAL: The user will put their Gemini/OpenAI API keys in a `.env` file; you must ensure they never accidentally push this to GitHub).
* Any `.pdf`, `.png`, or generated `.md` files located inside test or sample directories.

### 3. Strict "Token Preservation" Development Milestones

Do not attempt to write the entire application and call the LLM API on your first try. You will bankrupt the user's API limit debugging syntax errors. You will deliver this software to the user in 4 distinct verification checkpoints:

* **Checkpoint 1 (The Shell):** Deliver the repo structure, the `pyproject.toml`, and a mock entry point. *Success metric:* The user types `slidescribe --version` in their terminal and it prints `0.1.0`.
* **Checkpoint 2 (The Eye):** Deliver the PDF-to-Image rasterizer logic. *Success metric:* The user runs `slidescribe test.pdf` and it successfully creates `test_slides/` filled with `slide_1.png` to `slide_N.png` without crashing.
* **Checkpoint 3 (The Brain):** Deliver the Pydantic structured LLM API call. Test it on *one single image*.
* **Checkpoint 4 (The Assembly):** Deliver the Markdown compiler that stitches the JSON responses into the final `.md` document.

*Do not proceed from one checkpoint to the next until the user types: "Checkpoint X verified, proceed."*

### 4. Cross-Platform Pathing Safety

The user operates across both **Linux** and **Windows**.

* You are forbidden from using string concatenation for file paths (e.g., `folder + '/' + filename`).
* You must use `pathlib.Path` exclusively.
* When generating the relative Markdown image links inside the final output file, force standard forward slashes regardless of the host OS, as Markdown viewers break on Windows backslashes: `f"./{img_folder.name}/{img_file.name}"`.

### 5. The "Grand Finale" Milestone (The Showcase Demo)

Once Checkpoint 4 is verified and the tool works 100%, your final task before closing this session is to help the user prepare the **GitHub Flex**.

You will instruct the user to create a folder called `showcase/`. Inside it, we will put:

1. `bad_slide_sample.pdf` (A super messy slide with a complex diagram and a blurry math equation).
2. The generated `bad_slide_sample.md`
3. The `bad_slide_sample_slides/` image folder.

You will then write a dedicated section for the `README.md` called **"The Salvage Test"** that displays a side-by-side Markdown comparison of the blurry PDF screenshot next to the beautifully rendered, clean LaTeX output your code generated.

---

**Confirm you understand these 5 directives by replying with the proposed file-tree for the root directory.**