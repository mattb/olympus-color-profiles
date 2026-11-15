#pragma once
#include <stdexcept>
#include <string>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
// OM Workspace2.5.0.2 arm64 native desktop export ordering.
// Inputs decoder/property/context are borrowed. Return value owns one IOlyImage
// reference; caller must Release it. Temporary images and filters are released.
// No custom pixel math, no app state reads, no disk writes occur here.
namespace omw_desktop {
static void* method(void*object,unsigned index,const char*name){
    if(!object)throw std::runtime_error(std::string("Null native object for ")+name);
    void*fn=(*(void***)object)[index];Dl_info info{};
    if(!dladdr(fn,&info)||!info.dli_sname||!std::strstr(info.dli_sname,name))
        throw std::runtime_error(std::string("Unsupported installed native ABI: ")+name);
    return fn;
}
static void check(int status,const char*stage){if(status){char text[192];std::snprintf(text,sizeof(text),"%s failed (0x%08x)",stage,(unsigned)status);throw std::runtime_error(text);}}
struct Ref {
    void*p=nullptr;
    Ref()=default;explicit Ref(void*x):p(x){}
    Ref(const Ref&)=delete;Ref&operator=(const Ref&)=delete;
    ~Ref(){if(p)((unsigned(*)(void*))(*(void***)p)[4])(p);}
    void*detach(){void*out=p;p=nullptr;return out;}
};
static void factory(const char*iid,Ref&out){
    auto create=(int(*)(void*,void**))dlsym(RTLD_DEFAULT,"OlyIP2_CreateInstance");void*id=dlsym(RTLD_DEFAULT,iid);
    if(!create||!id)throw std::runtime_error(std::string("Installed image processor symbol missing: ")+iid);
    check(create(id,&out.p),iid);if(!out.p)throw std::runtime_error("Native filter factory returned null");
}
static void filter(Ref&f,void*input,Ref&output){
    check(((int(*)(void*,void*))method(f.p,16,"Prepare"))(f.p,input),"Native filter Prepare");
    check(((int(*)(void*,void**,void*,const void*,void*,bool,void*,int))method(f.p,5,"DoFilter"))(f.p,&output.p,input,nullptr,nullptr,true,nullptr,0),"Native filter DoFilter");
    if(!output.p)throw std::runtime_error("Native filter produced no image");
}
static void* develop(void*decoder,void*property,unsigned rotation,void*gpuContext,unsigned bits,unsigned subSampling=1,bool applyMFTS=true,void*(*beforeRGB)(void*,void*)=nullptr,void*filterContext=nullptr){
    if(rotation%90||rotation>=360)throw std::runtime_error("Desktop rotation must be0/90/180/270");
    if(bits!=8&&bits!=16)throw std::runtime_error("Desktop development requires8 or16bit samples");
    // The desktop app's shader-based MFTS operates AFTER physical orientation.
    // Internal distortion before orientation causes sparse16bit discrepancies.
    check(((int(*)(void*,bool))method(decoder,39,"SetApplyMFTSDistortion"))(decoder,false),"Disable internal MFTS");
    check(((int(*)(void*,bool))method(decoder,45,"SetConvertYCbCrToRGB"))(decoder,false),"Disable internal YCbCr conversion");
    check(((int(*)(void*,void*))method(decoder,62,"SetGPUContext"))(decoder,gpuContext),"Set decoder GPU context");
    Ref raw;
    check(((int(*)(void*,void**,unsigned,unsigned,unsigned,unsigned,bool,unsigned))method(decoder,15,"GetImage"))(decoder,&raw.p,0,bits,3,subSampling,false,0),"Develop native RAW");
    if(!raw.p)throw std::runtime_error("Native RAW development produced no image");
    if(rotation){
        auto rotate=(int(*)(void**,void*,int,void*))dlsym(RTLD_DEFAULT,"OlyIP2_RightAngledRotate");
        if(!rotate)throw std::runtime_error("Installed RightAngledRotate unavailable");
        // First arg nullable output; second is IOlyImage* (NOT IOlyImage**).
        // Null output means physically rotate the variable input image in place.
        check(rotate(nullptr,raw.p,(int)rotation,nullptr),"Orient native developed image");
    }
    Ref corrected;void*source=raw.p;
    if(applyMFTS){
        Ref mfts;factory("IID_IOlyIPFilterMFTSDistortion",mfts);
        check(((int(*)(void*,void*))method(mfts.p,40,"SetGPUContext"))(mfts.p,gpuContext),"Set MFTS GPU context");
        check(((int(*)(void*,void*))method(mfts.p,32,"UpdateCoef"))(mfts.p,property),"Set MFTS source property");
        filter(mfts,source,corrected);source=corrected.p;
    }
    Ref styled;if(beforeRGB){styled.p=beforeRGB(source,filterContext);if(!styled.p)throw std::runtime_error("Native pre-RGB filter returned no image");source=styled.p;}
    Ref converter,output;factory("IID_IOlyIPFilterYCbCrToRGB",converter);
    filter(converter,source,output);
    return output.detach();
}
} // namespace omw_desktop
