# Project:  bitmap designer

### workflow

1. startup
    - Startup UI
        - Startup UI
            - display "Bitmap Designer" in ASCII art
            - current color reset to default (1)
            - menu commands:
                - [N]ew Bitmap // use key "1" by default, current_file set to Untitled.json
                - [O]pen Bitmap
                - [Q]uit // global command, works from anywhere
                    - Shows "Really quit? (y/N)"
                    - If yes and dirty: "Save file first? (Y/n)"
                        - Yes: Save UI → quit
                        - No: quit without saving
                    - If no: cancel quit (back to previous screen)
                    - If not dirty: quit immediately
    - Open UI (modal window)
        - if ~/bitmaps does not exist
            - Prompt: Create ~/bitmaps directory? (Y/n)
                - if yes
                    - create ~/bitmaps directory
                    - proceed to list .json files
                - if no
                    - Prompt: Use current directory? (Y/n)
                        - if yes
                            - proceed to list .json files in current directory
                        - if no
                            - return to Startup UI
        - list .json files in ~/bitmaps (or the last visited directory), sorted by last modified (newest first)
        - if none
            - Response: No .json files were found. [OK]
            - return to Startup UI
        - menu commands below content:
            - [up/down jk] - select file in list
            - [Enter] - open selected file
            - [Escape] - return to Startup UI
        - validate file when opening
            - if good
                - go to Main UI
            - if bad
                - Response: Invalid .json file format. [OK]
                - return to Startup UI
2. editor
    - Main UI
        - page title shows current filename: "Main Menu - filename.json"
        - menu commands below content:
            - [D]esign mode // Design UI
            - [K]ey // Bitmap key UI
            - [P]review // open/refresh the preview in a browser window
            - [S]ave file // Save UI
            - [G]enerate code // Code generation UI
            - [M]anage file // Manage file UI
            - [,] Configuration mode // Configuration UI
            - [Escape] back // Close UI
    - Design UI (Central UI space)
        - display bitmap grid sized by bounds (within the available terminal viewport)
        - cursor shows the color character (0-F) with reverse video
        - two text characters = 1 bitmap pixel in UI (for square appearance)
        - Note: pixelSize config only affects preview/output, not the text UI
        - all transparent by default
        - page title shows current filename: "Design Mode - filename.json"
        - menu commands below content:
            - [arrow keys / hjkl] - move cursor // in two dimensions
            - [shift arrow keys / hjkl] - move cursor (5px)
            - [ctrl arrow keys / hjkl] - move cursor (10px)
            - [option arrow keys / hjkl] - move cursor (20px)
            - [yuio] - scroll grid // in two dimensions
            - [shift yuio] - scroll grid (5px)
            - [ctrl yuio] - scroll grid (10px)
            - [option yuio] - scroll grid (20px)
            - [wasd] - ad = -/+ bitmap index number, ws = -10/+10 bitmap index number
            - [C]olor=N - select current color (N shows current color value) // Color UI
            - [space] - paint one bitmap pixel at the cursor position with the current color
            - [F]ill - flood fill (paint bucket style) with current color
            - [R]ectangle - paint rectangle from cursor with current color
                - menu commands below content:
                    - [arrow keys / hjkl] - select opposite rectangle corner
                    - [Enter] - save rectangle (return to Design UI)
                    - [Escape] - cancel rectangle (return to Design UI)
                - Notes:
                    - The rectangle corner selection can move into any quadrant around the cursor.
                    - The selection movement must be restricted within the bounds.
            - [P]review - open/refresh the preview in a browser window
            - [U]ndo - undo last action (dimmed when nothing to undo)
                - cursor position saved and restored with each undo/redo
                - status shows: "Before change #N of M" or "Already at oldest change"
            - [^R]edo - redo last undone action (dimmed when nothing to redo)
                - status shows: "After change #N of M" or "Already at newest change"
            - [Escape] - exit Design mode (return Main UI)
    - Bitmap key UI (modal window) // select a unique dataspace for a bitmap with its own data
        - Prompt: Enter a key (short string, no spaces).
            - [Enter] - save configuration
            - [Escape] - cancel/revert
        - Error handling message for invalid input:
            - Response: Please enter a valid key (no spaces). [OK]
    - Color UI (modal window)
        - select color from list (see Colors section)
            - [0-9A-F] - color by # // 0 = transparent
            - [Enter] - save configuration
            - [Escape] - cancel/revert
    - Save UI (modal window)
        - use ~/bitmaps by default (or the last visited directory)
        - enter/edit file name // use current name, or default to Untitled)
            - [Enter] - save configuration
                - if blank input
                    - restore current filename (or "Untitled" if new file) in input, with name selection
                    - do not save
                - if file already exists and is the current file
                    - save (overwrite)
                - if file already exists and is a different file
                    - Response: File already exists. [OK]
                    - stay in Save UI
                - if file does not exist
                    - save file
                    - Response: File saved. [OK]
                    - return to Main UI
            - [Escape] - cancel/revert
        - Error handling messages:
            - displayed on status bar
    - Code generation UI (modal window)
        - display configuration in modal/scrollable window
        - [Enter] - copy to clipboard
        - [Escape] - close modal window
    - Manage file UI (modal window)
        - provide file management options
            - [R]ename - rename file
        - enter/edit file name // pre-filled with current filename, name part selected/highlighted, cursor before .json
                - if blank/whitespace input
                    - Response: Please enter a valid filename. [OK]
                    - stay in rename UI
                - if new name is same as current name
                    - close (no-op)
                - if new name already exists
                    - Response: File already exists. [OK]
                    - stay in rename UI
                - if valid new name
                    - rename file
                    - Response: File renamed. [OK]
                    - return to Manage file UI
            - [D]elete - delete file
                - if file name already exists
                    - if yes
                        - Prompt: Are you sure? (y/N)
                            - if yes
                                - delete file
                                - Response: File deleted. [OK]
                                - return to Main UI
                            - if no
                                - do nothing (stay in Manage file UI)
                    - if no
                        - display error
            - [Escape] - cancel/revert
        - Error handling messages:
            - (show system error message)
    - Configuration UI (modal window)
        - page title shows current filename: "Configuration - filename.json"
        - shows current values in a right-aligned column, 2-character margin from longest label
        - values refresh on return from any sub-screen
        - [K]ey - bitmap key
            - enter a key (short string, no spaces)
            - [Enter] - save configuration
            - [Escape] - cancel/revert
        - [B]ounds
            - prompt for the width and height of the bitmap
                - default width: 10
                - default height: 10
                - min width: 2
                - min height: 2
                - max width: none
                - max height: none
            - [Enter] - save the configuration
                - Response: Configuration saved.  [OK]
            - [Escape] - cancel/revert the configuration
        - [C]ontext - output variable name for ctx (default "ctx")
            - prompt for the context variable name
            - [Enter] - save the configuration
                - Response: Configuration saved.  [OK]
            - [Escape] - cancel/revert the configuration
        - Variable [X] - output variable name for x (default "x")
            - prompt for the context variable name
            - [Enter] - save the configuration
                - Response: Configuration saved.  [OK]
            - [Escape] - cancel/revert the configuration
        - Variable [Y] - output variable name for y (default "y")
            - prompt for the context variable name
            - [Enter] - save the configuration
                - Response: Configuration saved.  [OK]
            - [Escape] - cancel/revert the configuration
        - [L]ocation - offset coordinates on preview window
            - prompt for the X, Y offset coordinates
            - [Enter] - save the configuration
                - Response: Configuration saved.  [OK]
            - [Escape] - cancel/revert the configuration
        - [P]alette - select color palette
            - shows list of available palettes (up to 9) from ~/.bitmapsrc
            - [1-9] - select palette by numerical key
            - Current selection is highlighted
            - [Enter] - save configuration
                - Response: Configuration saved.  [OK]
            - [Escape] - cancel/revert the configuration
        - Pixel [S]ize - pixel size
            - prompt for the bitmap pixel size (default 2x2 canvas pixels)
            - [Enter] - save the configuration
                - Response: Configuration saved.  [OK]
            - [Escape] - cancel/revert the configuration
    - Close UI (Escape from Main UI)
        - if no changes were made (file not dirty)
            - return to the Startup UI (no prompts)
        - if changes were made (file is dirty)
            - Prompt: Really close? (y/N)
                - if yes
                    - Prompt: Save file first? (Y/n)
                        - if yes
                            - Save UI → Startup UI (dirty bit cleared)
                        - if no
                            - Prompt: Are you sure? (y/N)
                                - if yes
                                    - return to the Startup UI (dirty bit cleared)
                                - if no
                                    - go back to Main UI, do not close
                - if no
                    - go back to Main UI, do not close
    - Quit UI (q from anywhere)
        - global command, works from any screen
        - if not dirty: quit immediately
        - if dirty:
            - Prompt: Really quit? (y/N)
                - if yes
                    - Prompt: Save file first? (Y/n)
                        - if yes: Save UI → quit
                        - if no: quit without saving
                - if no: cancel quit (back to previous screen)

### Technical Stack
- Python

### Preview
- generate a basic HTML page with a canvas
- include a meta refresh tag for automatic refresh
   - <meta http-equiv="refresh" content="2">
- write to temp directory
- open in default browser (cross-platform)
- press P to regenerate and refresh the preview

### UI Layout
- Title: centered horizontally, positioned on line 2 (one line from top of screen)
- Content: 3-character left margin
- Spacing: 2 blank lines between title and content
- Menu/instructions: one line below content
- Status line: at bottom of screen (when present)

### Colors
- 0 = transparent (resets pixel(s) to space in the UI and bitmap data)
    - Note: never actually paint transparent colors in the generated code.
- 16-color palette accessible by keyboard (0-F)
- Up to 9 palettes can be defined in ~/.bitmapsrc
- Palette selection available in Configuration UI ([P]alette)
- Select palettes by numerical key [1-9]
- Cursor shows the color character (0-F) with reverse video (not [] brackets)
- inspired by retro-style, 16-bit colors (e.g., black, white, green, magenta, blue, orange, blue, green, as seen in Apple II Plus HIRES graphics mode)

- palette example 1
    - 0  transparent          space
    - 1  black        #000000  .     (black)
    - 2  deep blue    #0f2a66  ▓     (navy)
    - 3  dark green   #5a5a00  ▒     (olive)
    - 4  cyan         #3fb1b1  ░     (teal)
    - 5  dark brown   #5c2a00  #     (sienna)
    - 6  tan          #d6b07a  +     (tan)
    - 7  aqua         #6ff0c8  ~     (aqua)
    - 8  maroon       #7a1717  X     (maroon)
    - 9  magenta      #a24aff  *     (fuchsia)
    - A  orange       #ff9a00  @     (orange)
    - B  light gray   #d2d2d2  .     (lightgray)
    - C  mid gray     #909090  :     (gray)
    - D  pink         #ff7a9a  %     (hotpink)
    - E  yellow       #ffd24a  =     (yellow)
    - F  white        #ffffff  ·     (white)

- palette example 2
    - 0  transparent          space
    - 1  black        #000000  .     (black)
    - 2  white        #FFFFFF  @     (white)
    - 3  red          #FF4A00  #     (orangered)
    - 4  yellow       #FFD24A  $     (gold)
    - 5  green        #5CFF4A  %     (chartreuse)
    - 6  cyan         #4AA8A8  ^     (cadetblue)
    - 7  magenta      #C24AFF  &     (mediumorchid)
    - 8  orange       #FF9A00  *     (darkorange)
    - 9  brown        #8A4B00  (     (sienna)
    - A  orange       #ff9a00  @     (orange)
    - B  light gray   #d2d2d2  .     (lightgray)
    - C  mid gray     #909090  :     (gray)
    - D  pink         #ff7a9a  %     (hotpink)
    - E  yellow       #ffd24a  =     (yellow)
    - F  white        #ffffff  ·     (white)

### Code Generation
- by default, the context variable is "ctx."
- use fillStyle and fillRect 
- from the upper left, scan from left to right, top to bottom
- find the largest possible rectangular blocks of the same color and use fillStyle/fillRect
- iterate with smaller rectangular blocks, etc., down to the configured pixel size until the entire area is covered

### JSON File Format
    {
        "version": "1.0",
        "bitmaps": {
            "1": {
                "bounds": {"width": 10, "height": 10},
                "context": "ctx",
                "x": "x1",
                "y": "y1",
                "location": {"x": 0, "y": 0},
                "pixelSize": 2,
                "bitmap": {
                    "pixels": [
                        "^^^^^^^^^^",
                        "^^^^^^^^^^",
                        "^^^^^^^^^^",
                        "^^^^^^^^^^",
                        "^^^^^^^^^^",
                        "^^^^^^^^^^",
                        "^^^^^^^^^^",
                        "^^^^^^^^^^",
                        "^^^^^^^^^^",
                        "^^^^^^^^^^"
                    ],
                },
            },
            "42": {
                "bounds": {"width": 7, "height": 8},
                "context": "ctx",
                "x": "x42",
                "y": "y42",
                "location": {"x": 0, "y": 100},
                "pixelSize": 2,
                "bitmap": {
                    "pixels": [
                        ".....@@@@@",
                        ".....@@@@@",
                        ".....@@@@@",
                        ".....@@@@@",
                        ".....@@@@@",
                        "@@@@@.....",
                        "@@@@@.....",
                        "@@@@@.....",
                        "@@@@@.....",
                        "@@@@@....."
                    ],
                },
            },
        }
    }
- group data by bitmap key
    - one bitmap per bitmap key
    - each bitmap should contain pixel data
    - each bitmap should have configurations alongside it
- the bitmap should be saved as ASCII art
    - each character represents a canvas pixel: color codes 1-F are single characters, transparent (color code 0) is stored as a space character
    - In text UI: 2 characters = 1 pixel (for square appearance)
    - pixelSize config only affects preview/output, not text UI
    - colors
        - 16-color palette (0-F) for keyboard accessibility
        - 0 = transparent (space in UI and bitmap pixel data)

### Example Output Snippet
   // Fill a 10x10 design area with blue pixels.
   x1 = 0;
   y1 = 0;
   ctx.fillStyle('blue');
   ctx.fillRect(x1 + 0, y1 + 0, 10, 10);
   // Make a 2x2 checkerboard in a 10x10 design area.
   x42 = 0;
   y42 = 100;
   ctx.fillStyle('white');
   ctx.fillRect(x42 + 0, y42 + 0, 5, 5);
   ctx.fillRect(x42 + 5, y42 + 5, 5, 5);
   ctx.fillStyle('black');
   ctx.fillRect(x42 + 5, y42 + 0, 5, 5);
   ctx.fillRect(x42 + 0, y42 + 5, 5, 5);

### Configuration File (~/.bitmapsrc)
- JSON format
- Stores:
    - Current palette selection
    - Custom palette definitions (up to 9, keys 1-9)
- Example:
    ```json
    {
        "current_palette": "1",
        "palettes": {
            "1": {
                "name": "Default Palette",
                "colors": {
                    "0": {"char": " ", "hex": "#000000", "name": "transparent"},
                    "1": {"char": ".", "hex": "#000000", "name": "black"},
                    ...
                }
            },
            "2": {
                "name": "Alternate Palette",
                "colors": { ... }
            },
            ...
            "9": { ... }
        }
    }
    ```

### Stories
- I want to build a text-based utility to design bitmaps and convert them into JS code, targeting the HTML5 Canvas 2D API (CanvasRenderingContext2D).
- I want to be able to create a new bitmap.
- I want to be able to open a bitmap file from a list of bitmaps that I have created.
- I want to store bitmaps in a directory called ~/bitmaps by default.
- When saving the bitmap, I want a prompt with the default directory or last directory used, with the option to modify it or just hit Enter to accept it.
- I want the bitmap data to be stored with .json extension.
- I want the bitmap data to be human-readable.
- I want to store multiple bitmap sets in the same file.
- I want each bitmap set to contain configuration metadata, such as bitmap key, bounds, context variable name, location, and pixel size).
- I want to be able to open a .json file and work with it.
- I want to save global configurations in ~/.bitmapsrc.
- I want to specify/define color palette(s) in ~/.bitmapsrc.

### Response Handling
- Always allow an empty space on a modal window to use for response messages.

### Error Handling
- Always allow an empty space on a modal window to use for error messages.
- Error messages should be red.

### Default Key Handling
- Any prompt showing (y/N) defaults to No - pressing Enter or n accepts the default (No).
- Any prompt showing (Y/n) defaults to Yes - pressing Enter or y accepts the default (Yes).
