# Roadmap

## Near-term
- [ ] `:` command bar — Vim-style command input for extended operations
  - `scroll` / `noscroll` — toggle scroll mode
  - `q` — quit
  - `q!` — force quit
  - `w` — save
  - `wq` — save and quit
  - `e` — exit Design Mode to Main UI
  - `help` — keybindings reference popup
  - `set step N` — set cursor/scroll step
  - `set key NAME` — switch to or create bitmap key

## From specs.md TODO
- [ ] ASCII art "Bitmap Designer" header
- [ ] Open UI: interactive `~/bitmaps` creation prompt
- [ ] Open UI: fallback to current directory when `~/bitmaps` missing
- [ ] Rectangle paint mode ([R])
- [ ] Palette selection in Configuration UI ([P])
- [ ] `~/.bitmapsrc` config file (palettes, preferences)
- [ ] Code generation: optimal rectangular blocks instead of per-pixel
- [ ] Red error messages
- [ ] JSON validation on file open
- [ ] Consistent 1-line status margin across all screens

## Future / stretch
- [ ] Preview improvements
- [ ] Export to image formats
- [ ] Layer support
- [ ] Custom keybinding configuration
