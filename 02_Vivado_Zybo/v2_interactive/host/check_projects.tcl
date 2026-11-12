foreach xpr {V:/02_Vivado_Zybo/ECG_ViT_Zybo/ECG_ViT_Zybo.xpr V:/02_Vivado_Zybo/v2_interactive/ECG_ViT_Zybo_v2/ECG_ViT_Zybo_v2.xpr} {
    open_project $xpr
    set missing 0
    foreach f [get_files -quiet -all -of_objects [get_filesets {sources_1 constrs_1}]] {
        if {![file exists $f]} { incr missing; if {$missing <= 5} { puts "MISSING: $f" } }
    }
    puts "CHECK [file tail $xpr]: top=[get_property top [current_fileset]] missing_source_files=$missing impl_status=[get_property STATUS [get_runs impl_1]]"
    close_project
}
