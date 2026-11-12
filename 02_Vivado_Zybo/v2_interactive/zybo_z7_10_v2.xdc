## Zybo Z7-10 constraints for the v2 interactive demo.
## Pin locations taken from the Digilent board files installed with Vivado
## (boards/Digilent/zybo-z7-10/1.1/part0_pins.xml).
##
## No create_clock on sysclk here: the Clocking Wizard IP already constrains its
## 125 MHz input. Defining it twice caused the v1 TIMING-6 critical warnings.

## 125 MHz system clock
set_property -dict { PACKAGE_PIN K17 IOSTANDARD LVCMOS33 } [get_ports { sysclk }]

## Buttons BTN0-BTN3 (BTN0 is also the reset)
set_property -dict { PACKAGE_PIN K18 IOSTANDARD LVCMOS33 } [get_ports { btn[0] }]
set_property -dict { PACKAGE_PIN P16 IOSTANDARD LVCMOS33 } [get_ports { btn[1] }]
set_property -dict { PACKAGE_PIN K19 IOSTANDARD LVCMOS33 } [get_ports { btn[2] }]
set_property -dict { PACKAGE_PIN Y16 IOSTANDARD LVCMOS33 } [get_ports { btn[3] }]

## Slide switches SW0-SW3
set_property -dict { PACKAGE_PIN G15 IOSTANDARD LVCMOS33 } [get_ports { sw[0] }]
set_property -dict { PACKAGE_PIN P15 IOSTANDARD LVCMOS33 } [get_ports { sw[1] }]
set_property -dict { PACKAGE_PIN W13 IOSTANDARD LVCMOS33 } [get_ports { sw[2] }]
set_property -dict { PACKAGE_PIN T16 IOSTANDARD LVCMOS33 } [get_ports { sw[3] }]

## LEDs LD0-LD3
set_property -dict { PACKAGE_PIN M14 IOSTANDARD LVCMOS33 } [get_ports { led[0] }]
set_property -dict { PACKAGE_PIN M15 IOSTANDARD LVCMOS33 } [get_ports { led[1] }]
set_property -dict { PACKAGE_PIN G14 IOSTANDARD LVCMOS33 } [get_ports { led[2] }]
set_property -dict { PACKAGE_PIN D18 IOSTANDARD LVCMOS33 } [get_ports { led[3] }]

## RGB LED6 (board file rgb_led index 2,1,0 = V16,F17,M17)
set_property -dict { PACKAGE_PIN V16 IOSTANDARD LVCMOS33 } [get_ports { led6_r }]
set_property -dict { PACKAGE_PIN F17 IOSTANDARD LVCMOS33 } [get_ports { led6_g }]
set_property -dict { PACKAGE_PIN M17 IOSTANDARD LVCMOS33 } [get_ports { led6_b }]

## Human-speed inputs and indicator outputs: no I/O timing requirement.
## (AXI GPIO double-synchronizes its inputs internally.)
set_false_path -from [get_ports { btn[*] sw[*] }]
set_false_path -to   [get_ports { led[*] led6_r led6_g led6_b }]
