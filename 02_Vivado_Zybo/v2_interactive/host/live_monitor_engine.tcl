# Vivado-side engine for live_monitor.py (v2 interactive bitstream).
# Polls the firmware mailbox (BRAM 0x6000) and the AXI GPIO (LEDs, switches,
# buttons) over JTAG-to-AXI and prints one line whenever something changes:
#   POLL <13 mailbox words 0x6000-0x6030> <gpio_out> <gpio_in>      (hex)
# Arguments (-tclargs): <ltx file> <stop file> [<bit file> to program first]
# The loop ends when the stop file exists. Reading does not disturb the CPU.

lassign $argv ltx stopfile bitfile

proc say {msg} { puts $msg; flush stdout }

open_hw_manager
connect_hw_server -allow_non_jtag
open_hw_target
set dev [lindex [get_hw_devices xc7z010*] 0]
if {$dev eq ""} { say "FATAL no xc7z010 found on the JTAG chain (is the board on and connected?)"; exit 2 }
current_hw_device $dev

if {$bitfile ne "" && $bitfile ne "-"} {
    say "INFO programming $bitfile"
    set_property PROGRAM.FILE $bitfile $dev
    set_property PROBES.FILE $ltx $dev
    set_property FULL_PROBES.FILE $ltx $dev
    program_hw_devices $dev
    refresh_hw_device $dev
} else {
    set_property PROBES.FILE $ltx $dev
    set_property FULL_PROBES.FILE $ltx $dev
    refresh_hw_device -update_hw_probes false $dev
}

set ::axi [lindex [get_hw_axis] 0]
if {$::axi eq ""} { say "FATAL no JTAG-to-AXI master: program zybo_vit_v2_interactive.bit"; exit 3 }
reset_hw_axi $::axi

proc rd {addr len} {
    create_hw_axi_txn -force mon_rd $::axi -address [format %08X $addr] -len $len -type read
    run_hw_axi -quiet [get_hw_axi_txns mon_rd]
    set raw [string tolower [get_property DATA [get_hw_axi_txns mon_rd]]]
    # DATA comes back highest address first; return lowest address first.
    set words {}
    for {set i [expr {$len - 1}]} {$i >= 0} {incr i -1} {
        lappend words [string range $raw [expr {$i * 8}] [expr {$i * 8 + 7}]]
    }
    return $words
}

say "INFO connected"

# BTN0 resets the clock wizard, so the debug hub and the JTAG-to-AXI master lose
# their clock while it is held. Re-detect them until reads work again.
proc recover {} {
    while {![file exists $::stopfile]} {
        say "RECOVER"
        if {![catch {
            refresh_hw_device -update_hw_probes false $::dev
            set ::axi [lindex [get_hw_axis] 0]
            if {$::axi eq ""} { error "no axi master yet" }
            reset_hw_axi $::axi
            rd 0x6000 1
        } err]} {
            say "INFO reconnected"
            return
        }
        after 700
    }
}

set ::stopfile $stopfile
set ::dev $dev
set last ""
set n 0
while {![file exists $stopfile]} {
    if {[catch {
        set mb   [rd 0x6000 13]
        set gout [lindex [rd 0x40010000 1] 0]
        set gin  [lindex [rd 0x40010008 1] 0]
    } err]} {
        say "WARN read failed: [string range $err 0 120]"
        recover
        set last ""
        continue
    }
    set line "POLL [join $mb { }] $gout $gin"
    if {$line ne $last} { say $line; set last $line }
    incr n
    if {$n % 10 == 0} { say "ALIVE" }
    after 40
}
say "INFO stopped"
catch {close_hw_target}
catch {disconnect_hw_server}
exit 0
