## Bitmap Designer (Python)
A text-based utility to design bitmap graphics for JavaScript projects.

## Prerequisites
- Python 3.11 or higher

## Setup
1. (Optional) Create and activate a virtual environment:

   **macOS/Linux:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   **Windows:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install the project and dependencies:
   ```bash
   pip install -e .
   ```
   This installs the `bitmap-designer` CLI command and the required `textual` dependency.

## Running the Application
To run without installing (using the source directly):
```bash
python -m bitmap_designer
```

Or, install the project and run the CLI command:
```bash
pip install -e .
bitmap-designer
```

## Notes
- The app uses the [Textual](https://textual.textualize.io/) TUI framework, which requires a terminal with color and mouse support.
- Bitmap projects are saved as JSON files to `~/bitmaps` by default.
- Press `Q` from any screen to quit the application.
