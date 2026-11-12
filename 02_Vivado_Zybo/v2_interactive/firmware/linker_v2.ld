/* v2 firmware layout in the shared 32 KiB BRAM
 *   0x0000-0x5FFF  code, read-only data (stored beats), data, bss
 *   0x6000-0x6FFF  laptop mailbox + host beat buffer + accelerator output (fixed addresses)
 *   0x7000-0x7FEF  stack (grows down from 0x7FF0)
 */
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    BRAM (rwx) : ORIGIN = 0x00000000, LENGTH = 0x6000
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
    __stack_top = 0x7FF0;
    ASSERT(_end <= 0x6000, "Firmware overlaps the 0x6000 mailbox region")
}
