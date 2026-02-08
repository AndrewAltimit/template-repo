use anyhow::{Context, Result};
use clap::Parser;
use goblin::{
    container::{Container, Ctx, Endian},
    elf::{
        program_header::{PF_R, PF_W, PF_X, PT_LOAD},
        section_header::{SHT_NOBITS, SHT_NULL},
        Elf, Header, ProgramHeader, SectionHeader,
    },
    elf32,
};
use scroll::ctx::{IntoCtx, TryIntoCtx};
use std::{
    borrow::Cow,
    fs::{self, File},
    io::Write,
    iter,
    path::PathBuf,
};

const SHT_PRXREL: u32 = 0x7000_00A0;
const MODULE_INFO_SECTION: &str = ".rodata.sceModuleInfo";
const DATA_OFFSET: usize = elf32::header::SIZEOF_EHDR + elf32::program_header::SIZEOF_PHDR;

#[derive(Debug, Clone)]
struct Section<'a> {
    header: Cow<'a, SectionHeader>,
    data: Cow<'a, [u8]>,
    name: Cow<'a, str>,
}

#[derive(Parser, Debug)]
#[command(
    name = "prxmin",
    author = "Marko Mijalkovic <marko.mijalkovic97@gmail.com>",
    version = "0.1",
    about = "Minify (and strip) PRX files"
)]
struct Args {
    #[arg(name = "module.prx", help = "PRX module to minify")]
    input: PathBuf,
    #[arg(
        name = "minified.prx.min",
        help = "Optional output file name (default adds .min)"
    )]
    output: Option<PathBuf>,
}

fn run() -> Result<()> {
    let args = Args::parse();
    let bin = fs::read(&args.input)
        .with_context(|| format!("failed to read PRX: {}", args.input.display()))?;
    let elf = Elf::parse(&bin).context("failed to parse ELF from PRX")?;

    let shstrtab = {
        let idx = elf.header.e_shstrndx as usize;
        let sh = elf
            .section_headers
            .get(idx)
            .context("shstrtab index out of bounds")?;
        let start = sh.sh_offset as usize;
        let size = sh.sh_size as usize;
        &bin[start..start + size]
    };

    let sections = elf
        .section_headers
        .iter()
        .map(|header| {
            let start = header.sh_offset as usize;
            let size = header.sh_size as usize;

            let end = shstrtab[header.sh_name..]
                .iter()
                .position(|&b| b == 0)
                .context("unterminated section name in shstrtab")?;

            let bytes = &shstrtab[header.sh_name..header.sh_name + end];
            let name = std::str::from_utf8(bytes).context("invalid UTF-8 in section name")?;

            Ok(Section {
                header: Cow::Borrowed(header),
                data: Cow::Borrowed(&bin[start..start + size]),
                name: Cow::Borrowed(name),
            })
        })
        .collect::<Result<Vec<_>>>()?;

    let null = &sections[0];

    let allocated = sections
        .iter()
        .filter(|s| s.header.is_alloc())
        .filter(|s| s.header.sh_type != SHT_NOBITS);

    let relocations = sections
        .iter()
        .filter(|s| s.header.sh_type == SHT_PRXREL)
        .filter(|s| sections[s.header.sh_info as usize].header.is_alloc());

    let nobits = sections.iter().filter(|s| s.header.sh_type == SHT_NOBITS);

    let mut shstrtab = Section {
        data: Cow::Owned(Vec::new()),
        ..sections[elf.header.e_shstrndx as usize].clone()
    };

    let mut new_sections = Some(null)
        .into_iter()
        .chain(allocated)
        .chain(nobits)
        .chain(relocations)
        .cloned()
        .collect::<Vec<_>>();

    for section in &mut new_sections {
        section.header.to_mut().sh_name = shstrtab.data.len();

        // Add name and null byte.
        shstrtab.data.to_mut().extend(section.name.as_bytes());
        shstrtab.data.to_mut().extend(&[0]);
    }

    // Add shstrtab to itself.
    shstrtab.header.to_mut().sh_name = shstrtab.data.len();
    shstrtab.data.to_mut().extend(shstrtab.name.as_bytes());
    shstrtab.data.to_mut().extend(&[0]);
    shstrtab.header.to_mut().sh_size = shstrtab.data.len() as u64;

    new_sections.push(shstrtab);

    let names = new_sections
        .iter()
        .map(|s| s.name.clone())
        .collect::<Vec<_>>();

    // Fix relocation sh_info index.
    for s in new_sections
        .iter_mut()
        .filter(|s| s.header.sh_type == SHT_PRXREL)
    {
        let old_idx = s.header.sh_info as usize;
        let old_name = &sections
            .get(old_idx)
            .with_context(|| format!("relocation sh_info index {} out of bounds", old_idx))?
            .name;

        let idx = names
            .iter()
            .position(|n| n == old_name)
            .with_context(|| {
                format!(
                    "relocation target section '{}' not found in output",
                    old_name
                )
            })?;

        s.header.to_mut().sh_info = idx as u32;
        s.header.to_mut().sh_link = 0;
    }

    let mut body = Vec::<u8>::new();

    for section in &mut new_sections {
        if section.header.sh_type == SHT_NULL {
            continue;
        }

        let align = section.header.sh_addralign as usize;

        if align > 0 {
            // Add padding.
            let padding = (align - ((body.len() + DATA_OFFSET) & (align - 1))) & (align - 1);
            let padding = iter::repeat(0).take(padding);
            body.extend(padding);
        }

        section.header.to_mut().sh_offset = (DATA_OFFSET + body.len()) as u64;

        if section.header.sh_type == SHT_NOBITS {
            continue;
        }

        // Fill in the actual bytes.
        body.extend(section.data.as_ref());
    }

    let text_start = new_sections[1].header.sh_offset;

    let p_paddr = new_sections
        .iter()
        .find(|s| s.name == MODULE_INFO_SECTION)
        .map(|s| s.header.sh_offset)
        .context("missing .rodata.sceModuleInfo section")?;

    let p_filesz = new_sections
        .iter()
        .rev()
        .find(|s| s.header.sh_type != SHT_NOBITS && s.header.is_alloc())
        .map(|s| s.header.sh_offset + s.header.sh_size - text_start)
        .context("no allocated sections found")?;

    let p_memsz = new_sections
        .iter()
        .rev()
        .find(|s| s.header.sh_type == SHT_NOBITS)
        .map(|s| s.header.sh_offset + s.header.sh_size - text_start)
        .unwrap_or(p_filesz);

    let p_align = new_sections
        .iter()
        .map(|s| s.header.sh_addralign)
        .max()
        .context("no sections to compute alignment")?;

    let program_header = ProgramHeader {
        p_type: PT_LOAD,
        p_flags: PF_R | PF_W | PF_X,
        p_vaddr: 0,
        p_paddr,
        p_offset: new_sections[1].header.sh_offset,
        p_filesz,
        p_memsz,
        p_align,
    };

    let header = Header {
        e_shstrndx: new_sections.len() as u16 - 1,
        e_phoff: elf32::header::SIZEOF_EHDR as u64,
        e_shoff: (DATA_OFFSET + body.len()) as u64,
        e_phnum: 1,
        e_shnum: new_sections.len() as u16,
        ..elf.header
    };

    let ctx = Ctx {
        container: Container::Little,
        le: Endian::Little,
    };

    let out_file = args.output.unwrap_or(args.input.with_extension(".prx.min"));
    let mut out = File::create(&out_file)
        .with_context(|| format!("failed to create output: {}", out_file.display()))?;

    let mut buf = vec![0; elf32::header::SIZEOF_EHDR];
    header.into_ctx(&mut buf, ctx);
    out.write_all(&buf).context("failed to write ELF header")?;

    let mut buf = vec![0; elf32::program_header::SIZEOF_PHDR];
    program_header
        .try_into_ctx(&mut buf, ctx)
        .context("failed to serialize program header")?;
    out.write_all(&buf)
        .context("failed to write program header")?;

    out.write_all(&body).context("failed to write body")?;

    let mut buf = vec![0; elf32::section_header::SIZEOF_SHDR];

    for section in new_sections {
        section.header.into_owned().into_ctx(&mut buf, ctx);
        out.write_all(&buf)
            .context("failed to write section header")?;
    }

    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e:#}");
        std::process::exit(1);
    }
}
