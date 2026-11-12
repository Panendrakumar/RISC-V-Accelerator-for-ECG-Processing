// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2023.2 (64-bit)
// Tool Version Limit: 2023.10
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XVIT_INFERENCE_FIXED_H
#define XVIT_INFERENCE_FIXED_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
#ifndef __linux__
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#else
#include <stdint.h>
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stddef.h>
#endif
#include "xvit_inference_fixed_hw.h"

/**************************** Type Definitions ******************************/
#ifdef __linux__
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#else
typedef struct {
#ifdef SDT
    char *Name;
#else
    u16 DeviceId;
#endif
    u64 Control_BaseAddress;
} XVit_inference_fixed_Config;
#endif

typedef struct {
    u64 Control_BaseAddress;
    u32 IsReady;
} XVit_inference_fixed;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XVit_inference_fixed_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XVit_inference_fixed_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XVit_inference_fixed_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XVit_inference_fixed_ReadReg(BaseAddress, RegOffset) \
    *(volatile u32*)((BaseAddress) + (RegOffset))

#define Xil_AssertVoid(expr)    assert(expr)
#define Xil_AssertNonvoid(expr) assert(expr)

#define XST_SUCCESS             0
#define XST_DEVICE_NOT_FOUND    2
#define XST_OPEN_DEVICE_FAILED  3
#define XIL_COMPONENT_IS_READY  1
#endif

/************************** Function Prototypes *****************************/
#ifndef __linux__
#ifdef SDT
int XVit_inference_fixed_Initialize(XVit_inference_fixed *InstancePtr, UINTPTR BaseAddress);
XVit_inference_fixed_Config* XVit_inference_fixed_LookupConfig(UINTPTR BaseAddress);
#else
int XVit_inference_fixed_Initialize(XVit_inference_fixed *InstancePtr, u16 DeviceId);
XVit_inference_fixed_Config* XVit_inference_fixed_LookupConfig(u16 DeviceId);
#endif
int XVit_inference_fixed_CfgInitialize(XVit_inference_fixed *InstancePtr, XVit_inference_fixed_Config *ConfigPtr);
#else
int XVit_inference_fixed_Initialize(XVit_inference_fixed *InstancePtr, const char* InstanceName);
int XVit_inference_fixed_Release(XVit_inference_fixed *InstancePtr);
#endif

void XVit_inference_fixed_Start(XVit_inference_fixed *InstancePtr);
u32 XVit_inference_fixed_IsDone(XVit_inference_fixed *InstancePtr);
u32 XVit_inference_fixed_IsIdle(XVit_inference_fixed *InstancePtr);
u32 XVit_inference_fixed_IsReady(XVit_inference_fixed *InstancePtr);
void XVit_inference_fixed_EnableAutoRestart(XVit_inference_fixed *InstancePtr);
void XVit_inference_fixed_DisableAutoRestart(XVit_inference_fixed *InstancePtr);

void XVit_inference_fixed_Set_ecg_q10(XVit_inference_fixed *InstancePtr, u64 Data);
u64 XVit_inference_fixed_Get_ecg_q10(XVit_inference_fixed *InstancePtr);
void XVit_inference_fixed_Set_rr_q10(XVit_inference_fixed *InstancePtr, u64 Data);
u64 XVit_inference_fixed_Get_rr_q10(XVit_inference_fixed *InstancePtr);
void XVit_inference_fixed_Set_logits_q10(XVit_inference_fixed *InstancePtr, u64 Data);
u64 XVit_inference_fixed_Get_logits_q10(XVit_inference_fixed *InstancePtr);

void XVit_inference_fixed_InterruptGlobalEnable(XVit_inference_fixed *InstancePtr);
void XVit_inference_fixed_InterruptGlobalDisable(XVit_inference_fixed *InstancePtr);
void XVit_inference_fixed_InterruptEnable(XVit_inference_fixed *InstancePtr, u32 Mask);
void XVit_inference_fixed_InterruptDisable(XVit_inference_fixed *InstancePtr, u32 Mask);
void XVit_inference_fixed_InterruptClear(XVit_inference_fixed *InstancePtr, u32 Mask);
u32 XVit_inference_fixed_InterruptGetEnabled(XVit_inference_fixed *InstancePtr);
u32 XVit_inference_fixed_InterruptGetStatus(XVit_inference_fixed *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
