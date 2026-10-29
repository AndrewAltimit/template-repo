//! Font parsing, metrics and glyph rasterization.
//!
//! Fonts are read with `skrifa` (the maintained Google Fonts "fontations"
//! stack) and glyph outlines are rasterized with `ab_glyph_rasterizer`. The
//! metrics deliberately match the previous `ab_glyph` implementation so that
//! layout and fitting did not change when it was replaced (`ab_glyph` is built
//! on `ttf-parser`, which is unmaintained, RUSTSEC-2026-0192):
//!
//! - A pixel size is the distance from the line's ascender to its descender,
//!   not the em size.
//! - The ascender and descender come from `OS/2` when the font sets
//!   `USE_TYPO_METRICS`, and from `hhea` otherwise.
//! - Kerning comes from the first horizontal, non-variable `kern` subtable
//!   with a value for the pair (`GPOS` kerning needs a shaper and is not read).

use ab_glyph_rasterizer::{Rasterizer, point};
use skrifa::raw::TableProvider;
use skrifa::raw::tables::kern::SubtableKind;
use skrifa::{DrawMemory, GlyphId, PathSink, ScalerFont};

/// A parsed font. Cloning is cheap: the font data is shared.
#[derive(Clone)]
pub struct Face {
    font: skrifa::font::Font,
    /// Ascender in font units (positive, above the baseline).
    ascent: f32,
    /// Descender in font units (negative, below the baseline).
    descent: f32,
}

impl Face {
    /// Parse a font from owned bytes (the first font of a collection).
    pub fn from_vec(data: Vec<u8>) -> Result<Self, String> {
        Self::new(skrifa::font::Font::new(data, 0))
    }

    /// Parse a font from static bytes, e.g. one compiled into the binary.
    pub fn from_static(data: &'static [u8]) -> Result<Self, String> {
        Self::new(skrifa::font::Font::new(data, 0))
    }

    fn new(font: Option<skrifa::font::Font>) -> Result<Self, String> {
        let font = font.ok_or("not a supported font file")?;
        let line = font
            .metrics()
            .h_line()
            .ok_or("font has no horizontal line metrics")?;
        let (ascent, descent) = (line.ascender.to_f32(), line.descender.to_f32());
        if ascent - descent <= 0.0 {
            return Err("font has a zero line height".to_string());
        }
        Ok(Self {
            font,
            ascent,
            descent,
        })
    }

    /// The font at `size` px, where `size` is the ascender-to-descender height.
    pub fn scaled(&self, size: f32) -> ScaledFace<'_> {
        let tables = self.font.tables();
        let kern = tables
            .kern()
            .map(|kern| {
                kern.subtables()
                    .filter_map(Result::ok)
                    .filter(|st| st.is_horizontal() && !st.is_variable())
                    .filter_map(|st| st.kind().ok())
                    .collect()
            })
            .unwrap_or_default();
        ScaledFace {
            face: self,
            charmap: self.font.charmap(),
            glyph_metrics: self.font.glyph_metrics(),
            kern,
            factor: size / (self.ascent - self.descent),
        }
    }
}

/// A [`Face`] at one pixel size.
pub struct ScaledFace<'a> {
    face: &'a Face,
    charmap: skrifa::font::charmap::Charmap<'a>,
    glyph_metrics: skrifa::font::metrics::GlyphMetrics<'a>,
    kern: Vec<SubtableKind<'a>>,
    /// Pixels per font unit.
    factor: f32,
}

impl ScaledFace<'_> {
    /// Glyph for `c`, or [`GlyphId::NOTDEF`] when the font has none.
    pub fn glyph_id(&self, c: char) -> GlyphId {
        self.charmap.map_unicode(c).unwrap_or(GlyphId::NOTDEF)
    }

    /// Distance from the baseline up to the line's top, in px.
    pub fn ascent(&self) -> f32 {
        self.face.ascent * self.factor
    }

    /// Distance from the baseline down to the line's bottom (negative), in px.
    pub fn descent(&self) -> f32 {
        self.face.descent * self.factor
    }

    /// Horizontal advance of `id`, in px.
    pub fn h_advance(&self, id: GlyphId) -> f32 {
        self.glyph_metrics.h_advance(id) * self.factor
    }

    /// Kerning adjustment between `first` and `second`, in px.
    pub fn kern(&self, first: GlyphId, second: GlyphId) -> f32 {
        self.kern
            .iter()
            .find_map(|st| match st {
                SubtableKind::Format0(t) => t.kerning(first, second),
                SubtableKind::Format2(t) => t.kerning(first, second),
                SubtableKind::Format3(t) => t.kerning(first, second),
                SubtableKind::Format1(_) => None,
            })
            .map_or(0.0, |v| v as f32 * self.factor)
    }

    /// Outline of `id` with its origin at (`x`, `baseline`) in image space,
    /// or `None` for a glyph with no contours (such as a space).
    pub fn outline_glyph(
        &self,
        scaler: &ScalerFont,
        id: GlyphId,
        x: f32,
        baseline: f32,
    ) -> Option<OutlinedGlyph> {
        let mut sink = CurveSink::default();
        scaler
            .outline(id)?
            .draw(DrawMemory::Scratch, &mut sink)
            .ok()?;
        sink.close();
        let [x_min, y_min, x_max, y_max] = sink.bounds?;
        // Invalid bounds are treated as having no outline.
        if !(x_min < x_max && y_min < y_max) {
            return None;
        }
        // Use the subpixel fraction in floor/ceil rounding so identical
        // subpixel positions round identically.
        let (x_trunc, x_fract) = (x.trunc(), x.fract());
        let (y_trunc, y_fract) = (baseline.trunc(), baseline.fract());
        let f = self.factor;
        let bounds = PxBounds {
            min_x: (x_min * f + x_fract).floor() + x_trunc,
            min_y: (y_max * -f + y_fract).floor() + y_trunc,
            max_x: (x_max * f + x_fract).ceil() + x_trunc,
            max_y: (y_min * -f + y_fract).ceil() + y_trunc,
        };
        Some(OutlinedGlyph {
            curves: sink.curves,
            factor: f,
            origin: (x - bounds.min_x, baseline - bounds.min_y),
            bounds,
        })
    }

    /// Unhinted scaler in font units, for [`Self::outline_glyph`].
    pub fn outline_scaler(&self) -> ScalerFont {
        ScalerFont::unhinted(self.face.font.clone(), None)
    }
}

/// Whole-pixel bounding box of an outlined glyph, in image space.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PxBounds {
    pub min_x: f32,
    pub min_y: f32,
    pub max_x: f32,
    pub max_y: f32,
}

/// A glyph outline positioned and scaled for drawing.
pub struct OutlinedGlyph {
    /// Curves in font units, y up.
    curves: Vec<Curve>,
    /// Pixels per font unit.
    factor: f32,
    /// Glyph origin relative to the top-left of `bounds`.
    origin: (f32, f32),
    bounds: PxBounds,
}

impl OutlinedGlyph {
    /// Pixel bounds; [`Self::draw`] covers exactly this rectangle.
    pub fn px_bounds(&self) -> PxBounds {
        self.bounds
    }

    /// Call `o(x, y, coverage)` for every pixel inside [`Self::px_bounds`],
    /// with `x`, `y` relative to its top-left corner.
    pub fn draw(&self, o: impl FnMut(u32, u32, f32)) {
        let w = (self.bounds.max_x - self.bounds.min_x) as usize;
        let h = (self.bounds.max_y - self.bounds.min_y) as usize;
        let (ox, oy) = self.origin;
        let f = self.factor;
        let px = |(x, y): (f32, f32)| point(x * f + ox, y * -f + oy);
        let mut r = Rasterizer::new(w, h);
        for curve in &self.curves {
            match *curve {
                Curve::Line(p0, p1) => r.draw_line(px(p0), px(p1)),
                Curve::Quad(p0, p1, p2) => r.draw_quad(px(p0), px(p1), px(p2)),
                Curve::Cubic(p0, p1, p2, p3) => r.draw_cubic(px(p0), px(p1), px(p2), px(p3)),
            }
        }
        r.for_each_pixel_2d(o);
    }
}

#[derive(Debug, Clone, Copy)]
enum Curve {
    Line((f32, f32), (f32, f32)),
    Quad((f32, f32), (f32, f32), (f32, f32)),
    Cubic((f32, f32), (f32, f32), (f32, f32), (f32, f32)),
}

/// Collects outline curves and the bounds of every point (on and off curve).
#[derive(Default)]
struct CurveSink {
    curves: Vec<Curve>,
    last: (f32, f32),
    last_move: Option<(f32, f32)>,
    /// `[x_min, y_min, x_max, y_max]` over all points seen.
    bounds: Option<[f32; 4]>,
}

impl CurveSink {
    fn extend(&mut self, (x, y): (f32, f32)) {
        self.bounds = Some(match self.bounds {
            None => [x, y, x, y],
            Some([x0, y0, x1, y1]) => [x0.min(x), y0.min(y), x1.max(x), y1.max(y)],
        });
    }
}

impl PathSink for CurveSink {
    fn move_to(&mut self, x: f32, y: f32) {
        // Some fonts leave contours implicitly closed.
        self.close();
        self.extend((x, y));
        self.last = (x, y);
        self.last_move = Some(self.last);
    }

    fn line_to(&mut self, x: f32, y: f32) {
        self.extend((x, y));
        self.curves.push(Curve::Line(self.last, (x, y)));
        self.last = (x, y);
    }

    fn quad_to(&mut self, cx0: f32, cy0: f32, x: f32, y: f32) {
        self.extend((cx0, cy0));
        self.extend((x, y));
        self.curves.push(Curve::Quad(self.last, (cx0, cy0), (x, y)));
        self.last = (x, y);
    }

    fn curve_to(&mut self, cx0: f32, cy0: f32, cx1: f32, cy1: f32, x: f32, y: f32) {
        self.extend((cx0, cy0));
        self.extend((cx1, cy1));
        self.extend((x, y));
        self.curves
            .push(Curve::Cubic(self.last, (cx0, cy0), (cx1, cy1), (x, y)));
        self.last = (x, y);
    }

    fn close(&mut self) {
        if let Some(start) = self.last_move.take()
            && start != self.last
        {
            self.curves.push(Curve::Line(self.last, start));
            self.last = start;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn face() -> Face {
        Face::from_static(crate::fonts::EMBEDDED_FONT).expect("embedded font parses")
    }

    #[test]
    fn rejects_non_font_data() {
        assert!(Face::from_vec(b"not a font".to_vec()).is_err());
        assert!(Face::from_vec(Vec::new()).is_err());
    }

    #[test]
    fn size_is_ascender_to_descender_height() {
        let f = face();
        let s = f.scaled(50.0);
        assert!((s.ascent() - s.descent() - 50.0).abs() < 1e-3);
        assert!(s.ascent() > 0.0 && s.descent() < 0.0);
    }

    #[test]
    fn reads_kern_table() {
        // DejaVu Sans Bold kerns "AV" tighter in its `kern` table.
        let f = face();
        let s = f.scaled(40.0);
        assert!(s.kern(s.glyph_id('A'), s.glyph_id('V')) < 0.0);
        assert_eq!(s.kern(s.glyph_id('H'), s.glyph_id('H')), 0.0);
    }

    #[test]
    fn outlines_cover_their_bounds() {
        let f = face();
        let s = f.scaled(40.0);
        let scaler = s.outline_scaler();
        assert!(
            s.outline_glyph(&scaler, s.glyph_id(' '), 0.0, 40.0)
                .is_none()
        );
        let g = s
            .outline_glyph(&scaler, s.glyph_id('O'), 10.5, 40.0)
            .expect("O has an outline");
        let b = g.px_bounds();
        assert!(b.min_x >= 10.0 && b.max_x > b.min_x && b.max_y <= 41.0 && b.min_y < 40.0);
        let (mut max, mut cells) = (0.0f32, 0usize);
        g.draw(|_, _, c| {
            max = max.max(c);
            cells += 1;
        });
        assert_eq!(cells, ((b.max_x - b.min_x) * (b.max_y - b.min_y)) as usize);
        assert!(max > 0.99);
    }
}
