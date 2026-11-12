// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2023.2 (64-bit)
// Tool Version Limit: 2023.10
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef __linux__

#include "xstatus.h"
#ifdef SDT
#include "xparameters.h"
#endif
#include "xvit_inference_fixed.h"

extern XVit_inference_fixed_Config XVit_inference_fixed_ConfigTable[];

#ifdef SDT
XVit_inference_fixed_Config *XVit_inference_fixed_LookupConfig(UINTPTR BaseAddress) {
	XVit_inference_fixed_Config *ConfigPtr = NULL;

	int Index;

	for (Index = (u32)0x0; XVit_inference_fixed_ConfigTable[Index].Name != NULL; Index++) {
		if (!BaseAddress || XVit_inference_fixed_ConfigTable[Index].Control_BaseAddress == BaseAddress) {
			ConfigPtr = &XVit_inference_fixed_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XVit_inference_fixed_Initialize(XVit_inference_fixed *InstancePtr, UINTPTR BaseAddress) {
	XVit_inference_fixed_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XVit_inference_fixed_LookupConfig(BaseAddress);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XVit_inference_fixed_CfgInitialize(InstancePtr, ConfigPtr);
}
#else
XVit_inference_fixed_Config *XVit_inference_fixed_LookupConfig(u16 DeviceId) {
	XVit_inference_fixed_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XVIT_INFERENCE_FIXED_NUM_INSTANCES; Index++) {
		if (XVit_inference_fixed_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XVit_inference_fixed_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XVit_inference_fixed_Initialize(XVit_inference_fixed *InstancePtr, u16 DeviceId) {
	XVit_inference_fixed_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XVit_inference_fixed_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XVit_inference_fixed_CfgInitialize(InstancePtr, ConfigPtr);
}
#endif

#endif

