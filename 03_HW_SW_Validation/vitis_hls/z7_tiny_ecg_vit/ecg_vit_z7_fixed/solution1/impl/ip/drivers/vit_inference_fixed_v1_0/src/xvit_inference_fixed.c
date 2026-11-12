// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2023.2 (64-bit)
// Tool Version Limit: 2023.10
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xvit_inference_fixed.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XVit_inference_fixed_CfgInitialize(XVit_inference_fixed *InstancePtr, XVit_inference_fixed_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XVit_inference_fixed_Start(XVit_inference_fixed *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_AP_CTRL) & 0x80;
    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XVit_inference_fixed_IsDone(XVit_inference_fixed *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XVit_inference_fixed_IsIdle(XVit_inference_fixed *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XVit_inference_fixed_IsReady(XVit_inference_fixed *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XVit_inference_fixed_EnableAutoRestart(XVit_inference_fixed *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_AP_CTRL, 0x80);
}

void XVit_inference_fixed_DisableAutoRestart(XVit_inference_fixed *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_AP_CTRL, 0);
}

void XVit_inference_fixed_Set_ecg_q10(XVit_inference_fixed *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_ECG_Q10_DATA, (u32)(Data));
    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_ECG_Q10_DATA + 4, (u32)(Data >> 32));
}

u64 XVit_inference_fixed_Get_ecg_q10(XVit_inference_fixed *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_ECG_Q10_DATA);
    Data += (u64)XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_ECG_Q10_DATA + 4) << 32;
    return Data;
}

void XVit_inference_fixed_Set_rr_q10(XVit_inference_fixed *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_RR_Q10_DATA, (u32)(Data));
    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_RR_Q10_DATA + 4, (u32)(Data >> 32));
}

u64 XVit_inference_fixed_Get_rr_q10(XVit_inference_fixed *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_RR_Q10_DATA);
    Data += (u64)XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_RR_Q10_DATA + 4) << 32;
    return Data;
}

void XVit_inference_fixed_Set_logits_q10(XVit_inference_fixed *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_LOGITS_Q10_DATA, (u32)(Data));
    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_LOGITS_Q10_DATA + 4, (u32)(Data >> 32));
}

u64 XVit_inference_fixed_Get_logits_q10(XVit_inference_fixed *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_LOGITS_Q10_DATA);
    Data += (u64)XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_LOGITS_Q10_DATA + 4) << 32;
    return Data;
}

void XVit_inference_fixed_InterruptGlobalEnable(XVit_inference_fixed *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_GIE, 1);
}

void XVit_inference_fixed_InterruptGlobalDisable(XVit_inference_fixed *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_GIE, 0);
}

void XVit_inference_fixed_InterruptEnable(XVit_inference_fixed *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_IER);
    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_IER, Register | Mask);
}

void XVit_inference_fixed_InterruptDisable(XVit_inference_fixed *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_IER);
    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_IER, Register & (~Mask));
}

void XVit_inference_fixed_InterruptClear(XVit_inference_fixed *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_inference_fixed_WriteReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_ISR, Mask);
}

u32 XVit_inference_fixed_InterruptGetEnabled(XVit_inference_fixed *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_IER);
}

u32 XVit_inference_fixed_InterruptGetStatus(XVit_inference_fixed *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XVit_inference_fixed_ReadReg(InstancePtr->Control_BaseAddress, XVIT_INFERENCE_FIXED_CONTROL_ADDR_ISR);
}

