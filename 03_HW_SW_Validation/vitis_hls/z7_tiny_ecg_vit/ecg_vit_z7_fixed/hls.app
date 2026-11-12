<AutoPilot:project xmlns:AutoPilot="com.autoesl.autopilot.project" projectType="C/C++" top="vit_inference_fixed" name="ecg_vit_z7_fixed">
    <files>
        <file name="../../vit_inference_fixed_tb.cpp" sc="0" tb="1" cflags="-std=c++14 -I../../. -Wno-unknown-pragmas" csimflags="" blackbox="false"/>
        <file name="vit_inference_fixed.cpp" sc="0" tb="false" cflags="-std=c++14 -I." csimflags="" blackbox="false"/>
    </files>
    <solutions>
        <solution name="solution1" status=""/>
    </solutions>
    <Simulation argv="">
        <SimFlow name="csim" setup="false" optimizeCompile="false" clean="false" ldflags="" mflags=""/>
    </Simulation>
</AutoPilot:project>

