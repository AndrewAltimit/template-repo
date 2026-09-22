//! Markdown parsing: link extraction and anchor collection.
//!
//! Everything goes through pulldown-cmark, so code spans, fenced/indented
//! code blocks (any fence length, backticks or tildes), escaped brackets,
//! link titles and angle-bracket destinations are handled by a real
//! CommonMark parser instead of regexes.

use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::ops::Range;

use pulldown_cmark::{BrokenLink, CowStr, Event, LinkType, Options, Parser, Tag, TagEnd};

use crate::html::{self, Chunk, Marker};
use crate::slug::Slugger;

/// A unique link destination within one document.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Link {
    /// Destination exactly as written (after markdown unescaping).
    pub url: String,
    /// 1-based line numbers of every occurrence, ascending.
    pub lines: Vec<usize>,
}

/// A `[text][label]` or `[text][]` reference whose label has no definition.
/// GitHub renders these as literal text, so the author's link silently
/// disappears.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UndefinedReference {
    /// Source text of the reference, e.g. `[docs][missing]`.
    pub text: String,
    /// 1-based line number.
    pub line: usize,
}

/// Result of parsing one markdown document.
#[derive(Debug, Default)]
pub struct ParsedDocument {
    /// Unique link destinations, ordered by first occurrence.
    pub links: Vec<Link>,
    /// Fragment targets: GitHub heading slugs plus HTML `id`/`name` values.
    pub anchors: HashSet<String>,
    /// Full/collapsed references without a matching definition.
    pub undefined_references: Vec<UndefinedReference>,
}

/// Maps byte offsets to 1-based line numbers.
#[derive(Debug)]
pub struct LineIndex {
    starts: Vec<usize>,
}

impl LineIndex {
    /// Index the line starts of `content`.
    pub fn new(content: &str) -> Self {
        let starts = std::iter::once(0)
            .chain(content.match_indices('\n').map(|(i, _)| i + 1))
            .collect();
        Self { starts }
    }

    /// 1-based line containing byte `offset`.
    pub fn line(&self, offset: usize) -> usize {
        self.starts.partition_point(|&s| s <= offset)
    }
}

/// GitHub-flavored extensions relevant to link extraction.
fn options() -> Options {
    Options::ENABLE_TABLES
        | Options::ENABLE_FOOTNOTES
        | Options::ENABLE_STRIKETHROUGH
        | Options::ENABLE_TASKLISTS
}

/// Parse `content`, returning its links, anchors and undefined references.
///
/// Links inside regions disabled with `md-link-checker-disable` comments are
/// dropped here, so callers never see them.
pub fn parse_document(content: &str) -> ParsedDocument {
    let index = LineIndex::new(content);
    // (span, is_collapsed) of each reference whose label is undefined.
    let broken: RefCell<Vec<(Range<usize>, bool)>> = RefCell::new(Vec::new());
    let callback = |link: BrokenLink<'_>| -> Option<(CowStr<'_>, CowStr<'_>)> {
        match link.link_type {
            LinkType::Reference => broken.borrow_mut().push((link.span, false)),
            LinkType::Collapsed => broken.borrow_mut().push((link.span, true)),
            _ => {},
        }
        None
    };
    let parser = Parser::new_with_broken_link_callback(content, options(), Some(callback));

    // Every definition is a link even if nothing references it.
    let mut raw: Vec<(String, usize)> = parser
        .reference_definitions()
        .iter()
        .map(|(_, def)| (def.dest.to_string(), def.span.start))
        .collect();

    let mut collector = Collector::default();
    for (event, range) in parser.into_offset_iter() {
        collector.handle(event, range.start, &mut raw);
    }
    let Collector {
        mut anchors,
        markers,
        ..
    } = collector;

    let disabled = DisabledRegions::new(&markers, &index);
    let links = dedup_links(raw, &index, &disabled);

    let mut spans = broken.into_inner();
    spans.sort_by_key(|(s, _)| s.start);
    spans.dedup();
    let undefined_references = spans
        .into_iter()
        .filter(|(span, _)| !disabled.contains(span.start))
        .filter_map(|(span, collapsed)| {
            // The span of a collapsed reference stops before its `[]`.
            let end = if collapsed && content.get(span.end..).is_some_and(|r| r.starts_with("[]")) {
                span.end + 2
            } else {
                span.end
            };
            content.get(span.start..end).map(|text| UndefinedReference {
                text: text.to_string(),
                line: index.line(span.start),
            })
        })
        .collect();

    anchors.retain(|a| !a.is_empty());
    ParsedDocument {
        links,
        anchors,
        undefined_references,
    }
}

/// Parse only the fragment targets of `content`.
pub fn heading_anchors(content: &str) -> HashSet<String> {
    parse_document(content).anchors
}

/// Event-stream state machine.
#[derive(Default)]
struct Collector {
    slugger: Slugger,
    anchors: HashSet<String>,
    heading: Option<String>,
    image_depth: usize,
    html_block: Option<Vec<Chunk>>,
    markers: Vec<(Marker, usize)>,
}

impl Collector {
    fn handle(&mut self, event: Event<'_>, offset: usize, raw: &mut Vec<(String, usize)>) {
        match event {
            Event::Start(Tag::Link {
                link_type,
                dest_url,
                ..
            }) => push_destination(raw, link_type, &dest_url, offset),
            Event::Start(Tag::Image {
                link_type,
                dest_url,
                ..
            }) => {
                push_destination(raw, link_type, &dest_url, offset);
                self.image_depth += 1;
            },
            Event::End(TagEnd::Image) => self.image_depth = self.image_depth.saturating_sub(1),
            Event::Start(Tag::Heading { .. }) => self.heading = Some(String::new()),
            Event::End(TagEnd::Heading(_)) => {
                if let Some(text) = self.heading.take() {
                    let slug = self.slugger.slug(&text);
                    self.anchors.insert(slug);
                }
            },
            // Image alt text is not part of the rendered heading's text.
            Event::Text(text) | Event::Code(text) => {
                if self.image_depth == 0
                    && let Some(heading) = self.heading.as_mut()
                {
                    heading.push_str(&text);
                }
            },
            Event::SoftBreak | Event::HardBreak => {
                if let Some(heading) = self.heading.as_mut() {
                    heading.push(' ');
                }
            },
            Event::Start(Tag::HtmlBlock) => self.html_block = Some(Vec::new()),
            Event::End(TagEnd::HtmlBlock) => {
                if let Some(chunks) = self.html_block.take() {
                    self.absorb_html(&chunks, raw);
                }
            },
            Event::Html(text) => match self.html_block.as_mut() {
                Some(chunks) => chunks.push((text.to_string(), offset)),
                None => self.absorb_html(&[(text.to_string(), offset)], raw),
            },
            Event::InlineHtml(text) => self.absorb_html(&[(text.to_string(), offset)], raw),
            _ => {},
        }
    }

    fn absorb_html(&mut self, chunks: &[Chunk], raw: &mut Vec<(String, usize)>) {
        let findings = html::scan(chunks);
        raw.extend(findings.links);
        self.anchors.extend(findings.anchors);
        self.markers.extend(findings.markers);
    }
}

fn push_destination(
    raw: &mut Vec<(String, usize)>,
    link_type: LinkType,
    dest: &str,
    offset: usize,
) {
    let dest = dest.trim();
    if dest.is_empty() {
        return;
    }
    let url = match link_type {
        // `<user@example.com>` autolinks carry the bare address.
        LinkType::Email => format!("mailto:{dest}"),
        _ => dest.to_string(),
    };
    raw.push((url, offset));
}

/// Source ranges switched off by control comments.
struct DisabledRegions<'a> {
    /// Half-open byte ranges `[disable, enable)`.
    ranges: Vec<Range<usize>>,
    /// Lines excluded by `disable-next-line`.
    lines: HashSet<usize>,
    index: &'a LineIndex,
}

impl<'a> DisabledRegions<'a> {
    fn new(markers: &[(Marker, usize)], index: &'a LineIndex) -> Self {
        let mut sorted = markers.to_vec();
        sorted.sort_by_key(|&(_, off)| off);
        let mut ranges = Vec::new();
        let mut lines = HashSet::new();
        let mut open: Option<usize> = None;
        for (marker, off) in sorted {
            match marker {
                Marker::Disable => {
                    open.get_or_insert(off);
                },
                Marker::Enable => {
                    if let Some(start) = open.take() {
                        ranges.push(start..off);
                    }
                },
                Marker::DisableNextLine => {
                    lines.insert(index.line(off) + 1);
                },
            }
        }
        if let Some(start) = open {
            ranges.push(start..usize::MAX);
        }
        Self {
            ranges,
            lines,
            index,
        }
    }

    fn contains(&self, offset: usize) -> bool {
        self.ranges.iter().any(|r| r.contains(&offset))
            || (!self.lines.is_empty() && self.lines.contains(&self.index.line(offset)))
    }
}

fn dedup_links(
    raw: Vec<(String, usize)>,
    index: &LineIndex,
    disabled: &DisabledRegions,
) -> Vec<Link> {
    let mut links: Vec<Link> = Vec::new();
    let mut positions: HashMap<String, usize> = HashMap::new();
    for (url, offset) in raw {
        if disabled.contains(offset) {
            continue;
        }
        let line = index.line(offset);
        match positions.get(&url) {
            Some(&i) => links[i].lines.push(line),
            None => {
                positions.insert(url.clone(), links.len());
                links.push(Link {
                    url,
                    lines: vec![line],
                });
            },
        }
    }
    for link in &mut links {
        link.lines.sort_unstable();
        link.lines.dedup();
    }
    links.sort_by_key(|l| l.lines[0]);
    links
}

#[cfg(test)]
mod tests {
    use super::*;

    fn urls(content: &str) -> Vec<String> {
        parse_document(content)
            .links
            .into_iter()
            .map(|l| l.url)
            .collect()
    }

    #[test]
    fn extracts_all_link_forms() {
        let content = r#"# Test

[Inline](https://example.com "Title")
[Section](#introduction)
[Local](./local.md)
[Cross](./other.md#section)
![Image](https://example.com/image.png)
[Angle](<my file.md>)
<https://auto.example.com>
<user@example.com>
[Ref][r]

[r]: https://reference.com "Ref title"
[unused]: ./unused.md
"#;
        let got = urls(content);
        for want in [
            "https://example.com",
            "#introduction",
            "./local.md",
            "./other.md#section",
            "https://example.com/image.png",
            "my file.md",
            "https://auto.example.com",
            "mailto:user@example.com",
            "https://reference.com",
            "./unused.md",
        ] {
            assert!(got.iter().any(|u| u == want), "missing {want}: {got:?}");
        }
        // Titles never leak into the destination.
        assert!(!got.iter().any(|u| u.contains("Title")), "{got:?}");
    }

    #[test]
    fn ignores_code_of_every_kind() {
        let content = r#"
Normal [link](https://real.example.com)

```python
x = "[fake](https://fenced.example.com)"
```

~~~
[fake](https://tilde.example.com)
~~~

````md
```
[fake](https://nested.example.com)
```
````

    [fake](https://indented.example.com)

More `inline [code](https://inline.example.com)` and ``double `tick` [x](https://dbl.example.com)``
"#;
        assert_eq!(urls(content), ["https://real.example.com"]);
    }

    #[test]
    fn escaped_brackets_are_not_links() {
        assert!(urls(r"\[not a link\](nope.md)").is_empty());
    }

    #[test]
    fn footnotes_are_not_reference_definitions() {
        let content = "Text[^1].\n\n[^1]: Some explanatory note here.\n";
        assert!(urls(content).is_empty());
    }

    #[test]
    fn html_links_and_comments() {
        let content = r#"<p align="center"><img src="logo.png"></p>

Inline <a href="inline.md">x</a>.

<!-- [commented](gone.md) <a href="gone2.md"> -->
"#;
        assert_eq!(urls(content), ["logo.png", "inline.md"]);
    }

    #[test]
    fn line_numbers_and_dedup() {
        let content = "[a](x.md)\n\ntext\n[b](x.md) [c](y.md)\n";
        let doc = parse_document(content);
        assert_eq!(
            doc.links,
            [
                Link {
                    url: "x.md".into(),
                    lines: vec![1, 4]
                },
                Link {
                    url: "y.md".into(),
                    lines: vec![4]
                },
            ]
        );
    }

    #[test]
    fn disable_markers() {
        let content = r#"[a](a.md)
<!-- md-link-checker-disable -->
[b](b.md)
<!-- md-link-checker-enable -->
[c](c.md)
<!-- md-link-checker-disable-next-line -->
[d](d.md)
[e](e.md)
"#;
        assert_eq!(urls(content), ["a.md", "c.md", "e.md"]);
    }

    #[test]
    fn heading_anchors_basic() {
        let anchors = heading_anchors(
            "# Main Title\n\n## 1. Introduction\n\n### Sub-section A\n\n\
             ## 2. The Current Landscape (2025)\n",
        );
        for a in [
            "main-title",
            "1-introduction",
            "sub-section-a",
            "2-the-current-landscape-2025",
        ] {
            assert!(anchors.contains(a), "missing {a}: {anchors:?}");
        }
    }

    #[test]
    fn heading_anchors_duplicates_and_collisions() {
        let anchors = heading_anchors("## Foo\n\n## Foo\n\n## Foo 1\n\n## Details\n\n## Details\n");
        for a in ["foo", "foo-1", "foo-1-1", "details", "details-1"] {
            assert!(anchors.contains(a), "missing {a}: {anchors:?}");
        }
        assert_eq!(anchors.len(), 5);
    }

    #[test]
    fn heading_anchors_ignore_code_blocks() {
        let anchors = heading_anchors("# Real\n\n```markdown\n# Fake In Code\n```\n\n## Other\n");
        assert!(anchors.contains("real"));
        assert!(anchors.contains("other"));
        assert!(!anchors.contains("fake-in-code"));
    }

    #[test]
    fn heading_anchors_inline_formatting() {
        let anchors = heading_anchors(
            "## The `foo` Command\n\n## Layer 1: Shared (`wrapper-common`)\n\n\
             ### [API Reference](https://example.com)\n\n## **Bold** Heading\n\n\
             ## Logo ![alt text](logo.png) Section\n",
        );
        for a in [
            "the-foo-command",
            "layer-1-shared-wrapper-common",
            "api-reference",
            "bold-heading",
            "logo--section",
        ] {
            assert!(anchors.contains(a), "missing {a}: {anchors:?}");
        }
    }

    #[test]
    fn heading_anchors_setext_hard_break() {
        let anchors = heading_anchors("Word1\\\nWord2\n------\n");
        assert!(anchors.contains("word1-word2"), "{anchors:?}");
    }

    #[test]
    fn html_anchor_targets() {
        let anchors =
            heading_anchors("<a name=\"old-name\"></a>\n\n## New <a id=\"inline\"></a>\n");
        assert!(anchors.contains("old-name"));
        assert!(anchors.contains("inline"));
    }

    #[test]
    fn undefined_references_detected() {
        let content =
            "[ok][def] [bad][nope] [also bad][] [shortcut] - [x]\n\n[def]: https://x.test\n";
        let doc = parse_document(content);
        let texts: Vec<_> = doc
            .undefined_references
            .iter()
            .map(|r| r.text.as_str())
            .collect();
        assert_eq!(texts, ["[bad][nope]", "[also bad][]"]);
    }

    #[test]
    fn line_index() {
        let idx = LineIndex::new("a\nbc\n\nd");
        assert_eq!(idx.line(0), 1);
        assert_eq!(idx.line(2), 2);
        assert_eq!(idx.line(5), 3);
        assert_eq!(idx.line(6), 4);
    }
}
