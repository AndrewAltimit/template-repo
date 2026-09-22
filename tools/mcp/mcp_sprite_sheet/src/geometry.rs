//! Pure raster algorithms: lines, rectangles, ellipses, flood fill.
//!
//! Every function clips to a `width x height` canvas and only ever iterates
//! over O(canvas) or O(line length) cells, so hostile inputs such as a
//! rectangle a billion pixels wide or an ellipse with a huge radius cannot
//! hang the server or exhaust memory. Callers bound raw coordinates with
//! [`MAX_COORD`] so the arithmetic below cannot overflow.

/// Largest absolute coordinate / size accepted from tool arguments.
pub const MAX_COORD: i64 = 1 << 20;

/// Clip a rectangle to the canvas; returns `(x0, y0, x1, y1)` with exclusive
/// upper bounds, or `None` if nothing is visible.
pub fn clip_rect(x: i64, y: i64, w: i64, h: i64, cw: u32, ch: u32) -> Option<(u32, u32, u32, u32)> {
    if w <= 0 || h <= 0 {
        return None;
    }
    let x0 = x.max(0);
    let y0 = y.max(0);
    let x1 = (x + w).min(i64::from(cw));
    let y1 = (y + h).min(i64::from(ch));
    if x0 >= x1 || y0 >= y1 {
        return None;
    }
    Some((x0 as u32, y0 as u32, x1 as u32, y1 as u32))
}

#[inline]
fn in_canvas(x: i64, y: i64, cw: u32, ch: u32) -> bool {
    x >= 0 && y >= 0 && x < i64::from(cw) && y < i64::from(ch)
}

/// Bresenham line from `(x0, y0)` to `(x1, y1)` inclusive, clipped to the canvas.
///
/// Returns the in-canvas points and the number of points that fell outside.
pub fn line(x0: i64, y0: i64, x1: i64, y1: i64, cw: u32, ch: u32) -> (Vec<(u32, u32)>, usize) {
    let dx = (x1 - x0).abs();
    let dy = -(y1 - y0).abs();
    let sx = if x0 < x1 { 1 } else { -1 };
    let sy = if y0 < y1 { 1 } else { -1 };
    let mut err = dx + dy;
    let (mut x, mut y) = (x0, y0);
    let mut pts = Vec::new();
    let mut clipped = 0;
    loop {
        if in_canvas(x, y, cw, ch) {
            pts.push((x as u32, y as u32));
        } else {
            clipped += 1;
        }
        if x == x1 && y == y1 {
            break;
        }
        let e2 = 2 * err;
        if e2 >= dy {
            err += dy;
            x += sx;
        }
        if e2 <= dx {
            err += dx;
            y += sy;
        }
    }
    (pts, clipped)
}

/// Rectangle (outline or filled), clipped to the canvas.
pub fn rect(x: i64, y: i64, w: i64, h: i64, filled: bool, cw: u32, ch: u32) -> Vec<(u32, u32)> {
    let Some((x0, y0, x1, y1)) = clip_rect(x, y, w, h, cw, ch) else {
        return Vec::new();
    };
    let mut pts = Vec::new();
    if filled {
        for py in y0..y1 {
            for px in x0..x1 {
                pts.push((px, py));
            }
        }
        return pts;
    }
    let (left, top, right, bottom) = (x, y, x + w - 1, y + h - 1);
    for py in y0..y1 {
        let row_edge = i64::from(py) == top || i64::from(py) == bottom;
        if row_edge {
            for px in x0..x1 {
                pts.push((px, py));
            }
        } else {
            if left >= i64::from(x0) && left < i64::from(x1) {
                pts.push((left as u32, py));
            }
            if right != left && right >= i64::from(x0) && right < i64::from(x1) {
                pts.push((right as u32, py));
            }
        }
    }
    pts
}

/// Half-width of the ellipse span on row offset `dy`, or `None` outside it.
///
/// Uses effective radii `r + 0.4`, which produces the conventional pixel-art
/// shapes (radius 1 is a plus sign, radius 2 is a 5x5 rounded blob) and keeps
/// the extent along each axis exactly `r`. A zero radius degenerates to a
/// straight line (or a single pixel when both are zero).
pub fn ellipse_half_width(rx: i64, ry: i64, dy: i64) -> Option<i64> {
    if dy.abs() > ry {
        return None;
    }
    // Scale by 5 so r + 0.4 becomes the integer 5r + 2.
    let a = i128::from(5 * rx + 2);
    let b = i128::from(5 * ry + 2);
    let d = i128::from(5 * dy);
    let inside = |x: i64| {
        let x5 = i128::from(5 * x);
        x5 * x5 * b * b + d * d * a * a <= a * a * b * b
    };
    let ratio = (dy as f64) / (ry as f64 + 0.4);
    let mut x = ((rx as f64 + 0.4) * (1.0 - ratio * ratio).max(0.0).sqrt()).floor() as i64;
    x = x.clamp(0, rx);
    while x > 0 && !inside(x) {
        x -= 1;
    }
    while x < rx && inside(x + 1) {
        x += 1;
    }
    Some(x)
}

/// Ellipse centered at `(cx, cy)` with radii `(rx, ry)`, clipped to the canvas.
///
/// The outline is the set of filled pixels that have at least one
/// 4-neighbor outside the shape, which yields a closed, gap-free,
/// single-pixel-wide (8-connected) contour at every size.
pub fn ellipse(
    cx: i64,
    cy: i64,
    rx: i64,
    ry: i64,
    filled: bool,
    cw: u32,
    ch: u32,
) -> Vec<(u32, u32)> {
    let mut pts = Vec::new();
    if rx < 0 || ry < 0 {
        return pts;
    }
    // Only rows that intersect the canvas.
    let row_lo = (cy - ry).max(0);
    let row_hi = (cy + ry).min(i64::from(ch) - 1);
    let max_x = i64::from(cw) - 1;
    let push_span = |pts: &mut Vec<(u32, u32)>, y: i64, a: i64, b: i64| {
        let a = a.max(0);
        let b = b.min(max_x);
        for x in a..=b {
            pts.push((x as u32, y as u32));
        }
    };
    for y in row_lo..=row_hi {
        let dy = y - cy;
        let Some(hw) = ellipse_half_width(rx, ry, dy) else {
            continue;
        };
        if filled {
            push_span(&mut pts, y, cx - hw, cx + hw);
            continue;
        }
        let above = ellipse_half_width(rx, ry, dy - 1).unwrap_or(-1);
        let below = ellipse_half_width(rx, ry, dy + 1).unwrap_or(-1);
        let lo = hw.min(above.min(below) + 1);
        if lo == 0 {
            push_span(&mut pts, y, cx - hw, cx + hw);
        } else {
            push_span(&mut pts, y, cx - hw, cx - lo);
            push_span(&mut pts, y, cx + lo, cx + hw);
        }
    }
    pts
}

/// Compact bitset over canvas cells.
struct BitGrid {
    w: u32,
    bits: Vec<u64>,
}

impl BitGrid {
    fn new(w: u32, h: u32) -> Self {
        let n = (w as usize) * (h as usize);
        Self {
            w,
            bits: vec![0; n.div_ceil(64)],
        }
    }
    #[inline]
    fn idx(&self, x: u32, y: u32) -> usize {
        (y as usize) * (self.w as usize) + x as usize
    }
    #[inline]
    fn get(&self, x: u32, y: u32) -> bool {
        let i = self.idx(x, y);
        self.bits[i / 64] & (1 << (i % 64)) != 0
    }
    #[inline]
    fn set(&mut self, x: u32, y: u32) {
        let i = self.idx(x, y);
        self.bits[i / 64] |= 1 << (i % 64);
    }
}

/// Scanline flood fill: returns every 4-connected cell reachable from
/// `(sx, sy)` whose value (`get`) equals the start cell's value.
///
/// Empty cells (`None`) are a fillable "color" too. The caller must ensure the
/// start point is inside the canvas.
pub fn flood_region(
    cw: u32,
    ch: u32,
    sx: u32,
    sy: u32,
    get: impl Fn(u32, u32) -> Option<u8>,
) -> Vec<(u32, u32)> {
    let target = get(sx, sy);
    let matches = |x: u32, y: u32| get(x, y) == target;
    let mut seen = BitGrid::new(cw, ch);
    let mut out = Vec::new();
    let mut stack = vec![(sx, sy)];
    while let Some((x, y)) = stack.pop() {
        if seen.get(x, y) || !matches(x, y) {
            continue;
        }
        // Expand the run left and right.
        let mut l = x;
        while l > 0 && !seen.get(l - 1, y) && matches(l - 1, y) {
            l -= 1;
        }
        let mut r = x;
        while r + 1 < cw && !seen.get(r + 1, y) && matches(r + 1, y) {
            r += 1;
        }
        for px in l..=r {
            seen.set(px, y);
            out.push((px, y));
        }
        // Seed one point per matching run in the rows above and below.
        for ny in [y.checked_sub(1), (y + 1 < ch).then_some(y + 1)]
            .into_iter()
            .flatten()
        {
            let mut in_run = false;
            for px in l..=r {
                let ok = !seen.get(px, ny) && matches(px, ny);
                if ok && !in_run {
                    stack.push((px, ny));
                }
                in_run = ok;
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    fn set(pts: &[(u32, u32)]) -> HashSet<(u32, u32)> {
        pts.iter().copied().collect()
    }

    fn ascii(pts: &[(u32, u32)], w: u32, h: u32) -> Vec<String> {
        let s = set(pts);
        (0..h)
            .map(|y| {
                (0..w)
                    .map(|x| if s.contains(&(x, y)) { '#' } else { '.' })
                    .collect()
            })
            .collect()
    }

    #[test]
    fn line_horizontal_vertical_diagonal() {
        assert_eq!(line(0, 0, 5, 0, 16, 16).0.len(), 6);
        assert_eq!(line(2, 7, 2, 1, 16, 16).0.len(), 7);
        let (d, _) = line(0, 0, 3, 3, 16, 16);
        assert_eq!(d, vec![(0, 0), (1, 1), (2, 2), (3, 3)]);
    }

    #[test]
    fn line_single_point_and_reverse_symmetry() {
        assert_eq!(line(4, 4, 4, 4, 8, 8).0, vec![(4, 4)]);
        let a = set(&line(0, 0, 7, 3, 8, 8).0);
        let b = set(&line(7, 3, 0, 0, 8, 8).0);
        assert_eq!(a.len(), b.len());
    }

    #[test]
    fn line_clips_to_canvas() {
        let (pts, clipped) = line(-5, 2, 10, 2, 8, 8);
        assert_eq!(pts.len(), 8);
        assert_eq!(clipped, 8);
        assert!(pts.iter().all(|&(x, y)| x < 8 && y == 2));
    }

    #[test]
    fn rect_outline_and_filled() {
        let o = rect(1, 1, 4, 3, false, 8, 8);
        assert_eq!(set(&o).len(), 10); // 4+4 top/bottom + 2 sides
        let f = rect(1, 1, 4, 3, true, 8, 8);
        assert_eq!(f.len(), 12);
    }

    #[test]
    fn rect_degenerate_sizes() {
        assert!(rect(0, 0, 0, 5, false, 8, 8).is_empty());
        assert!(rect(0, 0, 5, -1, true, 8, 8).is_empty());
        assert_eq!(rect(0, 0, 1, 1, false, 8, 8), vec![(0, 0)]);
        assert_eq!(set(&rect(0, 0, 1, 4, false, 8, 8)).len(), 4);
        assert_eq!(set(&rect(0, 0, 3, 1, false, 8, 8)).len(), 3);
    }

    #[test]
    fn rect_huge_is_clipped_not_hung() {
        let pts = rect(-1_000_000, -1_000_000, 2_000_000, 2_000_000, true, 4, 4);
        assert_eq!(pts.len(), 16);
        // Outline with all edges off-canvas draws nothing.
        assert!(rect(-10, -10, 100, 100, false, 4, 4).is_empty());
        // Partially visible outline: only the left edge is in view.
        let pts = rect(2, -10, 100, 100, false, 4, 4);
        assert_eq!(set(&pts), set(&[(2, 0), (2, 1), (2, 2), (2, 3)]));
    }

    #[test]
    fn ellipse_small_circles_have_pixel_art_shapes() {
        assert_eq!(ellipse(1, 1, 0, 0, false, 3, 3), vec![(1, 1)]);
        assert_eq!(
            ascii(&ellipse(1, 1, 1, 1, false, 3, 3), 3, 3),
            vec![".#.", "#.#", ".#."]
        );
        assert_eq!(
            ascii(&ellipse(1, 1, 1, 1, true, 3, 3), 3, 3),
            vec![".#.", "###", ".#."]
        );
        assert_eq!(
            ascii(&ellipse(3, 3, 3, 3, false, 7, 7), 7, 7),
            vec![
                "..###..", ".#...#.", "#.....#", "#.....#", "#.....#", ".#...#.", "..###..",
            ]
        );
    }

    #[test]
    fn ellipse_zero_radius_is_line() {
        let pts = ellipse(2, 2, 0, 2, false, 5, 5);
        assert_eq!(set(&pts), set(&[(2, 0), (2, 1), (2, 2), (2, 3), (2, 4)]));
        let pts = ellipse(2, 2, 2, 0, true, 5, 5);
        assert_eq!(set(&pts).len(), 5);
    }

    #[test]
    fn ellipse_negative_radius_is_empty() {
        assert!(ellipse(2, 2, -1, 2, false, 5, 5).is_empty());
    }

    #[test]
    fn ellipse_extent_is_exact_and_symmetric() {
        for (rx, ry) in [(1, 1), (2, 5), (7, 3), (10, 10), (15, 4)] {
            let (w, h) = (2 * rx as u32 + 1, 2 * ry as u32 + 1);
            let pts = set(&ellipse(rx, ry, rx, ry, true, w, h));
            let min_x = pts.iter().map(|p| p.0).min().unwrap();
            let max_x = pts.iter().map(|p| p.0).max().unwrap();
            let min_y = pts.iter().map(|p| p.1).min().unwrap();
            let max_y = pts.iter().map(|p| p.1).max().unwrap();
            assert_eq!((min_x, max_x, min_y, max_y), (0, w - 1, 0, h - 1));
            for &(x, y) in &pts {
                assert!(pts.contains(&(w - 1 - x, y)), "h-symmetry {rx},{ry}");
                assert!(pts.contains(&(x, h - 1 - y)), "v-symmetry {rx},{ry}");
            }
        }
    }

    #[test]
    fn ellipse_outline_is_closed_boundary_of_fill() {
        for (rx, ry) in [(3, 3), (8, 2), (2, 9), (12, 7)] {
            let (w, h) = (2 * rx as u32 + 1, 2 * ry as u32 + 1);
            let fill = set(&ellipse(rx, ry, rx, ry, true, w, h));
            let outline = set(&ellipse(rx, ry, rx, ry, false, w, h));
            // Outline must be exactly the 4-boundary of the fill.
            for &(x, y) in &fill {
                let boundary = [(-1i64, 0i64), (1, 0), (0, -1), (0, 1)]
                    .iter()
                    .any(|(dx, dy)| {
                        let nx = x as i64 + dx;
                        let ny = y as i64 + dy;
                        nx < 0 || ny < 0 || !fill.contains(&(nx as u32, ny as u32))
                    });
                assert_eq!(outline.contains(&(x, y)), boundary, "({x},{y}) r={rx},{ry}");
            }
            // Flood-filling the outside of the outline must not leak inside.
            let center = (rx as u32, ry as u32);
            let region = flood_region(w, h, 0, 0, |x, y| outline.contains(&(x, y)).then_some(1));
            assert!(!set(&region).contains(&center), "outline leaks r={rx},{ry}");
        }
    }

    #[test]
    fn ellipse_huge_radius_is_clipped() {
        let pts = ellipse(0, 0, 900_000, 900_000, true, 16, 16);
        assert_eq!(pts.len(), 256);
        let pts = ellipse(0, 0, 900_000, 900_000, false, 16, 16);
        assert!(pts.is_empty(), "outline far outside the canvas");
    }

    #[test]
    fn flood_fill_respects_walls() {
        // Vertical wall at x=2 splits a 5x3 canvas.
        let wall: HashSet<(u32, u32)> = [(2, 0), (2, 1), (2, 2)].into_iter().collect();
        let region = flood_region(5, 3, 0, 0, |x, y| wall.contains(&(x, y)).then_some(7));
        assert_eq!(region.len(), 6);
        assert!(region.iter().all(|&(x, _)| x < 2));
    }

    #[test]
    fn flood_fill_on_colored_region_and_diagonal_gap() {
        // Filling a diagonal line's color only reaches 4-connected cells of that
        // color, so diagonal neighbors are not included.
        let diag: HashSet<(u32, u32)> = [(0, 0), (1, 1), (2, 2)].into_iter().collect();
        let region = flood_region(3, 3, 0, 0, |x, y| diag.contains(&(x, y)).then_some(1));
        assert_eq!(region, vec![(0, 0)]);
        // A diagonal line is a wall for 4-connected fills: the empty cells on
        // each side form separate regions.
        let region = flood_region(3, 3, 1, 0, |x, y| diag.contains(&(x, y)).then_some(1));
        assert_eq!(set(&region), set(&[(1, 0), (2, 0), (2, 1)]));
    }

    #[test]
    fn flood_fill_complex_shape_matches_naive() {
        // Spiral-ish maze to exercise scanline seeding.
        let w = 12;
        let h = 9;
        let walls: HashSet<(u32, u32)> = (0..w)
            .flat_map(|x| (0..h).map(move |y| (x, y)))
            .filter(|&(x, y)| (x * 7 + y * 3) % 5 == 0 && !(x == 0 && y == 0))
            .collect();
        let get = |x: u32, y: u32| walls.contains(&(x, y)).then_some(1u8);
        let fast = set(&flood_region(w, h, 0, 0, get));
        // Naive BFS reference.
        let mut naive = HashSet::new();
        let mut stack = vec![(0u32, 0u32)];
        while let Some((x, y)) = stack.pop() {
            if get(x, y).is_some() || !naive.insert((x, y)) {
                continue;
            }
            if x > 0 {
                stack.push((x - 1, y));
            }
            if x + 1 < w {
                stack.push((x + 1, y));
            }
            if y > 0 {
                stack.push((x, y - 1));
            }
            if y + 1 < h {
                stack.push((x, y + 1));
            }
        }
        assert_eq!(fast, naive);
    }

    #[test]
    fn clip_rect_cases() {
        assert_eq!(clip_rect(-2, -2, 4, 4, 10, 10), Some((0, 0, 2, 2)));
        assert_eq!(clip_rect(8, 8, 5, 5, 10, 10), Some((8, 8, 10, 10)));
        assert_eq!(clip_rect(10, 0, 5, 5, 10, 10), None);
        assert_eq!(clip_rect(0, 0, 0, 5, 10, 10), None);
    }
}
