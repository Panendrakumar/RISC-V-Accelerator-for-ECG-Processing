OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    BRAM (rwx) : ORIGIN = 0x00000000, LENGTH = 32K
}

SECTIONS
{
    .text : ALIGN(4)
    {
        KEEP(*(.text.start))
        *(.text .text.*)
    } > BRAM

    .rodata : ALIGN(4)
    {
        *(.rodata .rodata.*)
        *(.srodata .srodata.*)
    } > BRAM

    .data : ALIGN(4)
    {
        *(.data .data.*)
        *(.sdata .sdata.*)
    } > BRAM

    .bss (NOLOAD) : ALIGN(4)
    {
        __bss_start = .;
        *(.bss .bss.*)
        *(.sbss .sbss.*)
        *(COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > BRAM

    . = ALIGN(16);
    _end = .;
    __stack_top = ORIGIN(BRAM) + LENGTH(BRAM) - 16;
    ASSERT(_end < __stack_top - 256, "Firmware and static buffers leave no stack space in BRAM")
}
