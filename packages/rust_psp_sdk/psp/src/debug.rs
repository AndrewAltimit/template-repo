//! Debug support.
//!
//! You should use the `dprintln!` and `dprint!` macros.
//!
//! Thread-safe: access to the character buffer is protected by a spinlock.

use crate::sys;
use core::cell::UnsafeCell;
use core::fmt;
use core::sync::atomic::{AtomicBool, Ordering};

/// Like `println!`, but prints to the PSP screen.
#[macro_export]
macro_rules! dprintln {
    () => {
        $crate::dprint!("\n")
    };
    ($($arg:tt)*) => {{
        $crate::dprint!($($arg)*);
        $crate::dprint!("\n");
    }};
}

/// Like `print!`, but prints to the PSP screen.
#[macro_export]
macro_rules! dprint {
    ($($arg:tt)*) => {{
        $crate::debug::print_args(core::format_args!($($arg)*))
    }}
}

/// A simple spinlock for single-core environments (PSP MIPS R4000).
///
/// Uses `AtomicBool` with acquire/release ordering. On the single-core PSP
/// this prevents compiler reordering; on multi-core it would provide proper
/// synchronization too.
struct SpinMutex<T> {
    locked: AtomicBool,
    data: UnsafeCell<T>,
}

// SAFETY: SpinMutex provides exclusive access via the atomic lock.
// PSP is single-core, so the spinlock prevents re-entrant access from
// interrupt handlers or coroutines that might call dprintln!.
unsafe impl<T: Send> Sync for SpinMutex<T> {}
unsafe impl<T: Send> Send for SpinMutex<T> {}

impl<T> SpinMutex<T> {
    const fn new(val: T) -> Self {
        Self {
            locked: AtomicBool::new(false),
            data: UnsafeCell::new(val),
        }
    }

    fn lock(&self) -> SpinGuard<'_, T> {
        while self
            .locked
            .compare_exchange_weak(false, true, Ordering::Acquire, Ordering::Relaxed)
            .is_err()
        {
            core::hint::spin_loop();
        }
        SpinGuard { mutex: self }
    }
}

struct SpinGuard<'a, T> {
    mutex: &'a SpinMutex<T>,
}

impl<T> core::ops::Deref for SpinGuard<'_, T> {
    type Target = T;
    fn deref(&self) -> &T {
        // SAFETY: We hold the lock.
        unsafe { &*self.mutex.data.get() }
    }
}

impl<T> core::ops::DerefMut for SpinGuard<'_, T> {
    fn deref_mut(&mut self) -> &mut T {
        // SAFETY: We hold the lock exclusively.
        unsafe { &mut *self.mutex.data.get() }
    }
}

impl<T> Drop for SpinGuard<'_, T> {
    fn drop(&mut self) {
        self.mutex.locked.store(false, Ordering::Release);
    }
}

static CHARS: SpinMutex<CharBuffer> = SpinMutex::new(CharBuffer::new());

/// Update the screen.
fn update(chars: &CharBuffer) {
    unsafe {
        init();
        clear_screen(0);

        for (i, line) in chars.lines().enumerate() {
            put_str::<MsxFont>(
                &line.chars[0..line.len],
                0,
                i * MsxFont::CHAR_HEIGHT,
                0xffff_ffff,
            )
        }
    }
}

trait Font {
    const CHAR_WIDTH: usize;
    const CHAR_HEIGHT: usize;

    fn put_char(x: usize, y: usize, color: u32, c: u8);
}

struct MsxFont;

impl Font for MsxFont {
    const CHAR_HEIGHT: usize = 10;
    const CHAR_WIDTH: usize = 6;

    fn put_char(x: usize, y: usize, color: u32, c: u8) {
        unsafe {
            let mut ptr = VRAM_BASE.add(x + y * BUFFER_WIDTH);

            for i in 0..8 {
                for j in 0..8 {
                    if MSX_FONT[c as usize * 8 + i] & (0b1000_0000 >> j) != 0 {
                        *ptr = color;
                    }

                    ptr = ptr.offset(1);
                }

                ptr = ptr.add(BUFFER_WIDTH - 8);
            }
        }
    }
}

use crate::constants::{
    SCREEN_HEIGHT, SCREEN_WIDTH, VRAM_BASE_UNCACHED, VRAM_BUFFER_WIDTH,
};

const BUFFER_WIDTH: usize = VRAM_BUFFER_WIDTH as usize;
const DISPLAY_HEIGHT: usize = SCREEN_HEIGHT as usize;
const DISPLAY_WIDTH: usize = SCREEN_WIDTH as usize;
static mut VRAM_BASE: *mut u32 = 0 as *mut u32;

#[allow(unsafe_op_in_unsafe_fn)]
unsafe fn clear_screen(color: u32) {
    let mut ptr = VRAM_BASE;

    for _ in 0..(BUFFER_WIDTH * DISPLAY_HEIGHT) {
        *ptr = color;
        ptr = ptr.offset(1);
    }
}

#[allow(unsafe_op_in_unsafe_fn)]
unsafe fn put_str<T: Font>(s: &[u8], x: usize, y: usize, color: u32) {
    if y > DISPLAY_HEIGHT {
        return;
    }

    for (i, c) in s.iter().enumerate() {
        if i >= (DISPLAY_WIDTH / T::CHAR_WIDTH) {
            break;
        }

        if *c as u32 <= 255 && *c != b'\0' {
            T::put_char(T::CHAR_WIDTH * i + x, y, color, *c);
        }
    }
}

#[allow(unsafe_op_in_unsafe_fn)]
unsafe fn init() {
    // The OR operation here specifies the address bypasses cache.
    VRAM_BASE = (VRAM_BASE_UNCACHED | sys::sceGeEdramGetAddr() as u32) as *mut u32;

    sys::sceDisplaySetMode(sys::DisplayMode::Lcd, DISPLAY_WIDTH, DISPLAY_HEIGHT);
    sys::sceDisplaySetFrameBuf(
        VRAM_BASE as *const u8,
        BUFFER_WIDTH,
        sys::DisplayPixelFormat::Psm8888,
        sys::DisplaySetBufSync::NextFrame,
    );
}

#[doc(hidden)]
pub fn print_args(arguments: core::fmt::Arguments<'_>) {
    use fmt::Write;

    let mut guard = CHARS.lock();
    let _ = write!(*guard, "{}", arguments);
    update(&guard);
}

const ROWS: usize = DISPLAY_HEIGHT / MsxFont::CHAR_HEIGHT;
const COLS: usize = DISPLAY_WIDTH / MsxFont::CHAR_WIDTH;

#[derive(Copy, Clone)]
struct Line {
    chars: [u8; COLS],
    len: usize,
}

impl Line {
    const fn new() -> Self {
        Self {
            chars: [0; COLS],
            len: 0,
        }
    }
}

struct CharBuffer {
    lines: [Line; ROWS],
    written: usize,
    advance_next: bool,
}

impl CharBuffer {
    const fn new() -> Self {
        Self {
            lines: [Line::new(); ROWS],
            written: 0,
            advance_next: false,
        }
    }

    fn advance(&mut self) {
        self.written += 1;
        if self.written >= ROWS {
            *self.current_line() = Line::new();
        }
    }

    fn current_line(&mut self) -> &mut Line {
        &mut self.lines[self.written % ROWS]
    }

    fn add(&mut self, c: u8) {
        if self.advance_next {
            self.advance_next = false;
            self.advance();
        }

        match c {
            b'\n' => self.advance_next = true,
            b'\t' => {
                self.add(b' ');
                self.add(b' ');
                self.add(b' ');
                self.add(b' ');
            }

            _ => {
                if self.current_line().len == COLS {
                    self.advance();
                }

                let line = self.current_line();
                line.chars[line.len] = c;
                line.len += 1;
            }
        }
    }

    fn lines(&self) -> LineIter<'_> {
        LineIter { buf: self, pos: 0 }
    }
}

impl fmt::Write for CharBuffer {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        for c in s.chars() {
            match c as u32 {
                0..=255 => self.add(c as u8),
                _ => self.add(0),
            }
        }

        Ok(())
    }
}

struct LineIter<'a> {
    buf: &'a CharBuffer,
    pos: usize,
}

impl<'a> Iterator for LineIter<'a> {
    type Item = Line;

    fn next(&mut self) -> Option<Self::Item> {
        if self.pos < core::cmp::min(self.buf.written + 1, ROWS) {
            let idx = if self.buf.written > ROWS {
                (self.buf.written + 1 + self.pos) % ROWS
            } else {
                self.pos
            };

            let line = self.buf.lines[idx];
            self.pos += 1;
            Some(line)
        } else {
            None
        }
    }
}

/// Raw MSX font.
///
/// This is an 8bit x 256 black and white image.
const MSX_FONT: [u8; 2048] = *include_bytes!("msxfont.bin");
