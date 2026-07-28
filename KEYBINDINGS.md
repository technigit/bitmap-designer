# Keybindings

## Design Mode

*(To be added)*

---

## Map Mode

Three composable layers. **Selection** is always on. **Zoom** and **Action** are toggled on/off independently.
Lower-layer keys pass through to the active layer unless overridden.

| Layer | Toggle | Purpose |
|---|---|---|
| Selection | *always on* | Navigate and select bitmaps by spatial position |
| Zoom | `` ` `` | Manipulate zoom/pan of the viewport |
| Action | `!` | Destructive operations (yank, put, delete) |

### Selection (base layer)

| Key | Action |
|---|---|
| `wasd` / `hjkl` / arrows | Select adjacent bitmap |
| `^` / `$` | Leftmost / rightmost bitmap in same row |
| `0` | Reset zoom |
| `1-9` | Count prefix (e.g. `5h` → select 5th bitmap to the left) |
| `Enter` | Select current key & exit map mode |
| `gg` / `1G` | Farthest upper-left bitmap |
| `G` | First bitmap on lowest populated row |
| `nG` | Nth row, leftmost bitmap |
| `g^` / `g$` | Viewport left / right visible key |
| `f` / `F` | Fit to selected key / Fit all to view |
| `/` | Find bitmap by name |
| `O` | Bitmap ops popup |
| `?` | Help |
| `Escape` | Back (exits Map Mode) |

### + Zoom (toggled by `` ` ``)

Overrides `hjkl`/arrows to pan instead of navigate. Everything else passes through from Selection.

| Key | Action |
|---|---|
| `hjkl` / arrows | Pan by 1 |
| `Shift+HJKL` / `Shift+arrows` | Fast pan 5 |
| `0` | Reset zoom |
| `+=` / `-=` | Zoom in / out |
| `R` | Reset pan |
| `~` | Toggle pan mode |
| `` ` `` | Disable Zoom |

### + Action (toggled by `!`)

Adds destructive key operations. All non-listed keys inherit from whatever lower-layer combination (Selection ± Zoom) is active.

| Key | Action |
|---|---|
| `y` / `yy` | Yank selected key |
| `p` / `P` | Put yanked key |
| `d` / `dd` | Delete selected key |
| `x` | Delete selected key (alt) |
| `v` | Visual multi-select (?) |
| `!` | Disable Action |
