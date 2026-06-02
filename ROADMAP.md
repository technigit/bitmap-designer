# Roadmap

## Shipped
- [x] Cursor hide/show (Tab toggle)
- [x] Consistent 1-line status margin across all screens
- [x] Palette management: per-file custom palettes with inheritance, hardcoded presets, palette editor, and palette resolution system
- [x] glyphmode display mode: palette glyph replaces raw color ID in pixel grids
- [x] `:` command bar — Vim-style command input for extended operations
  - [x] `q` / `q!` — quit / force quit
  - [x] `w` / `w!` — save / force save
  - [x] `wq` / `wq!` — save and quit
  - [x] `e` — exit to previous screen
  - [x] `help` — keybindings reference popup
  - [x] `scroll` / `noscroll` — toggle scroll mode
  - [x] `pan` / `nopan` — toggle pan mode
  - [x] `set step N` — set cursor/scroll step
  - [x] `set key NAME` — switch to or create bitmap key
  - [x] `set color C` — set current drawing color
  - [x] `set colorpixels [on|off|mixed]` — pixel display mode
  - [x] `info` — project metadata popup
  - [x] `close` / `close!` — close project / force close
  - [x] `config` / `config key NAME` — configuration UI
- [x] Rectangle paint mode ([R]) with live preview
- [x] Pixel display: swatches (`on`), colored numbers (`mixed`), plain (`off`)
- [x] `:info` popup with live `wasd` key switching
- [x] `:close` / `:close!` command with dirty-check confirmation
- [x] `!` express-exit key in close and quit confirmation popups
- [x] Map screen: zoom, pan, fit-to-selection, fit-all, find key
- [x] Map screen: pixel display respects color pixels mode

## In progress
- [ ] Tab completion in command bar

## Backlog (from specs.md TODO)
- [ ] ASCII art "Bitmap Designer" header
- [ ] Open UI: interactive `~/bitmaps` creation prompt
- [ ] Open UI: fallback to current directory when `~/bitmaps` missing
- [ ] `~/.bitmapsrc` config file (palettes, preferences)
- [ ] Code generation: optimal rectangular blocks instead of per-pixel
- [ ] Red error messages
- [ ] JSON validation on file open

## Future / stretch
- [ ] Preview improvements
- [ ] Export to image formats
- [ ] Layer support
- [ ] Custom keybinding configuration
