# Keybindings

## Design Mode

*(To be added)*

---

## Map Mode

Three composable layers. **Selection** is always on. **Zoom**, **Action**, and **Ghost** are toggled on/off independently.
Lower-layer keys pass through to the active layer unless overridden.
The view auto-scrolls minimally (with a small padding) to keep the selected bitmap visible while navigating and after puts / ghost places.

| Layer | Toggle | Purpose |
|---|---|---|
| Selection | *always on* | Navigate and select bitmaps by spatial position |
| Zoom | `` ` `` | Manipulate zoom/pan of the viewport |
| Action | `!` | Destructive operations (yank, put, delete) |
| Ghost | `@` | Place the yanked buffer anywhere with a movable preview |

### Selection (base layer)

| Key | Action |
|---|---|
| `wasd` / `hjkl` / arrows | Select adjacent bitmap |
| `space` | Select next bitmap to the right (like `l`) |
| `^` / `$` | Leftmost / rightmost bitmap in same row |
| `0` | Leftmost in row (reset zoom in Zoom mode) |
| `1-9` | Count prefix: `5h`/`3l`/`2j`/`3<space>` move N steps (clamped); `3gg` = `3G`; `20j` multi-digit works; count ignored on `^`/`$` |
| `Enter` | Select current key & exit map mode |
| `gg` / `1G` | Farthest upper-left bitmap |
| `G` | First bitmap on lowest populated row |
| `nG` | Nth row, leftmost bitmap |
| `g^` / `g$` | Viewport left / right visible key |
| `zz` | Center vertically (keep horizontal; reveal if off-screen) |
| `f` / `F` | Fit to selected key / Fit all to view |
| `/` | Find bitmap by name |
| `u` / `ctrl+z` | Undo last map change (delete / put / ghost place) |
| `ctrl+r` | Redo |
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
| `r` | Reset pan |
| `~` | Toggle pan mode |
| `` ` `` | Disable Zoom |

### + Action (toggled by `!`)

Adds destructive key operations. All non-listed keys inherit from whatever lower-layer combination (Selection ± Zoom) is active.

Yank (`y`) and delete (`d`) are vim-style operators: pressing one alone does nothing — follow it with a **motion** (or repeat it for the whole row). A count before the operator (`3dd`) or between operator and motion (`y3j`) multiplies the motion. Delete also yanks, so `p`/`P` restores what you removed.

| Key | Action |
|---|---|
| `y<space>` / `yl` | Yank selected key + N−1 to the right |
| `yh` | Yank N keys to the left (exclusive — never the selected key) |
| `yj` / `yk` | Yank current + N keys in the column below / above |
| `y^` / `y$` | Yank from leftmost in row → selected / selected → rightmost |
| `yy` / `Y` | Yank whole row (+ N−1 rows below with a count) |
| `d<motion>` | Same motions as `y`, but deletes (and yanks) |
| `dd` | Delete whole row (+ N−1 rows below with a count) |
| `x` | Delete selected key (alias for `d<space>`) |
| `p` / `P` | Put right/left (single key, row or selection; source layout preserved) |
| `v` | Visual multi-select (keys between anchor & cursor; `y`/`d` act on it) |
| `Enter` (visual) | Extend selection to end of row, then to start of next row |
| `!` | Disable Action |

Motions are row/column scoped by span-overlap (partial overlap counts). `h` is exclusive like vim; all other motions include the selected key. `Escape` cancels a pending operator.

### + Ghost (toggled by `@`)

Puts the current yank buffer at a movable preview. Entering ghost mode starts the preview at the selected key's location (the yank buffer's source keys stay highlighted). Movement is unclamped — the ghost can go anywhere, even over existing keys or past the map edge. The frame is green when free to place, red on collision. Enter commits and stays on (place multiple copies); `Escape` or `@` cancels.

Movement snaps to the grid by default; `Shift` gives fine 1-unit moves. The snap grid is built from existing keys' edges + the gutter gap (so `p`/`P` put locations are always snapped candidates); when no line exists in the move direction it extrapolates at the buffer's own size + gap, so the ghost keeps tiling even with a single key.

| Key | Action |
|---|---|
| `hjkl` / `wasd` / arrows / `space` | Snap to next alignment line in that direction (buffer size + gap fallback); count repeats the snap |
| `3j` / `2l` / etc. | Counted move (N steps) |
| `Shift` + move | Fine move by 1 (buffer size + gap fallback) |
| `0` / `^` / `$` | Snap to canvas left / right edge (nearest visible grid line) |
| `[` / `]` | Align to leftmost / rightmost visible key edge |
| `Enter` | Place buffer at ghost position (stays in ghost mode) |
| `Escape` / `@` | Cancel ghost mode |
