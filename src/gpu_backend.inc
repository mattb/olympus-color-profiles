#pragma once
#include <stdexcept>
#include <string>
#include <OpenCL/opencl.h>
// Standalone native GPU initialization for OM Workspace2.5.0.2 arm64.
// Requires Foundation, objc/message.h, objc/runtime.h, dlfcn.h, cstdio.
// Frameworks must already be initialized before invoking this helper.
// All proprietary code/resources stay in the installed app; no copied kernels.
struct OMWGPUBackend {
    void *resource=nullptr,*context=nullptr;
    id objcContext=nil;
    NSDictionary *metadata=nil;
};
static OMWGPUBackend initializeGPU(NSString *appRoot,unsigned platformIndex=0,unsigned deviceIndex=0) {
    OMWGPUBackend g;
    NSString*path=[appRoot stringByAppendingPathComponent:@"Contents/Frameworks/OlyHydrangea_arm.framework/OlyHydrangea_arm"];
    void*hyd=dlopen(path.fileSystemRepresentation,RTLD_NOW|RTLD_GLOBAL);
    if(!hyd)throw std::runtime_error(std::string("GPU framework: ")+dlerror());
    auto factory=(int(*)(void**))dlsym(hyd,"OlyGetHydrangeaInstance");
    auto load=(int(*)(void**,void*,unsigned,unsigned))dlsym(hyd,"OlyGetContextManagerWithLoadSource");
    if(!factory||!load)throw std::runtime_error("GPU installed factory symbols unavailable");
    int status=factory(&g.resource);
    if(status||!g.resource)throw std::runtime_error("GPU resource initialization failed");
    auto rv=*(void***)g.resource;unsigned platformCount=0;
    ((void(*)(void*,unsigned*))rv[9])(g.resource,&platformCount);
    if(platformIndex>=platformCount)throw std::runtime_error("GPU platform selection out of range");
    void*platform=nullptr;
    if(((int(*)(void*,void**,unsigned))rv[10])(g.resource,&platform,platformIndex)||!platform)throw std::runtime_error("GPU platform lookup failed");
    auto pv=*(void***)platform;unsigned deviceCount=0;
    ((void(*)(void*,unsigned*))pv[7])(platform,&deviceCount);
    if(deviceIndex>=deviceCount)throw std::runtime_error("GPU device selection out of range");
    void*device=nullptr;
    if(((int(*)(void*,void**,unsigned))pv[8])(platform,&device,deviceIndex)||!device)throw std::runtime_error("GPU device lookup failed");
    auto dv=*(void***)device;char name[512]={},vendor[512]={};int actual=0;unsigned long long memory=0;
    ((int(*)(void*,char*,int,int*))dv[6])(device,name,sizeof(name),&actual);
    ((int(*)(void*,unsigned long long*))dv[7])(device,&memory);
    ((int(*)(void*,char*,int,int*))dv[9])(device,vendor,sizeof(vendor),&actual);
    NSDate*start=[NSDate date];status=load(&g.context,g.resource,platformIndex,deviceIndex);
    if(status||!g.context)throw std::runtime_error("GPU source-program/context initialization failed");
    // getCommandQueue returns a pointer/reference to the native queue handle.
    auto cv=*(void***)g.context;void*queue=*(((void**(*)(void*,unsigned))cv[8])(g.context,0));
    void*clDevice=nullptr;unsigned long long clType=0;
    auto queueInfo=(int(*)(void*,unsigned,size_t,void*,size_t*))dlsym(RTLD_DEFAULT,"clGetCommandQueueInfo");
    auto deviceInfo=(int(*)(void*,unsigned,size_t,void*,size_t*))dlsym(RTLD_DEFAULT,"clGetDeviceInfo");
    if(!queueInfo||!deviceInfo||queueInfo(queue,CL_QUEUE_DEVICE,sizeof(clDevice),&clDevice,nullptr)||deviceInfo(clDevice,CL_DEVICE_TYPE,sizeof(clType),&clType,nullptr)||!(clType&CL_DEVICE_TYPE_GPU))throw std::runtime_error("Native OpenCL queue is not a GPU device");
    Class wrapper=objc_getClass("OlyOCLContextManager");
    if(!wrapper)throw std::runtime_error("Installed ObjC GPU context wrapper unavailable");
    g.objcContext=((id(*)(id,SEL))objc_msgSend)((id)wrapper,sel_registerName("alloc"));
    g.objcContext=((id(*)(id,SEL))objc_msgSend)(g.objcContext,sel_registerName("init"));
    ((void(*)(id,SEL,void*))objc_msgSend)(g.objcContext,sel_registerName("setContextManager:"),g.context);
    g.metadata=@{@"platform_index":@(platformIndex),@"device_index":@(deviceIndex),@"platform_count":@(platformCount),@"device_count":@(deviceCount),@"device_name":@(name),@"vendor_name":@(vendor),@"global_memory_bytes":@(memory),@"opencl_device_type":@(clType),@"program_source":@"installed encrypted Hydrangea1/2/3 resources via OlyGetContextManagerWithLoadSource",@"context_initialization_seconds":@(-[start timeIntervalSinceNow])};
    return g;
}
// Essential ordering: invoke before ANY OlyRawProcedure/OlyRawFileReader init.
// Callback sets flags before setupProcDC11WithExifInfo selects Peony (GPU).
// Omitting it selects Pomegranate(CPU), even if decoder GPUContext is later set.
static void configureRawProcedureStartup(const OMWGPUBackend&g) {
    id appContext=((id(*)(id,SEL))objc_msgSend)((id)objc_getClass("OlyGPUAppContext"),sel_registerName("sharedInstance"));
    id contextWrapper=g.objcContext;
    ((void(*)(id,SEL,id))objc_msgSend)(appContext,sel_registerName("setSetupRawProcedureBlock:"),^(id procedure){
        ((void(*)(id,SEL,BOOL))objc_msgSend)(procedure,sel_registerName("setUseGPU:"),YES);
        ((void(*)(id,SEL,id))objc_msgSend)(procedure,sel_registerName("setContextManager:"),contextWrapper);
    });
}
// Optional but matches the desktop decoder's separate GPU distortion context.
static void configureRawDecoderGPU(void*decoder,const OMWGPUBackend&g) {
    auto v=*(void***)decoder;
    int status=((int(*)(void*,void*))v[62])(decoder,g.context);
    if(status)throw std::runtime_error("Native raw decoder SetGPUContext failed");
}
