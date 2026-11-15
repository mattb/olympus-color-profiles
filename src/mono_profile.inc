#pragma once
#include "native_rng.inc"
// Installed OM Workspace2.5.0.2 arm64 native DC11 monochrome bindings.
// No pixel transforms. Requires Foundation/AppKit, objc runtime, need/ok/slot.
// Apply AFTER ORF inheritance, OES overlay and generic per-photo overrides,
// BEFORE proc.setToRawDecoder:. Never run COLOR/HSL setup after apply().
namespace omw_mono {
static void abi(id proc,const char*name,const char*encoding){Method m=class_getInstanceMethod(object_getClass(proc),sel_registerName(name));need(m&&!strcmp(method_getTypeEncoding(m),encoding),"unsupported native MONO ObjC ABI");}
static void setScalar(id p,const char*n,uint16_t v){abi(p,n,"i20@0:8S16");ok(((int(*)(id,SEL,uint16_t))objc_msgSend)(p,sel_registerName(n),v),n);}
static void setPair(id p,const char*n,uint16_t m,int16_t v,bool unsignedValue=false){abi(p,n,unsignedValue?"i24@0:8S16S20":"i24@0:8S16s20");ok(((int(*)(id,SEL,uint16_t,int16_t))objc_msgSend)(p,sel_registerName(n),m,v),n);}
static bool enabled(id p,const char*n){abi(p,n,"B16@0:8");return ((BOOL(*)(id,SEL))objc_msgSend)(p,sel_registerName(n));}
static NSArray* range(id p,const char*n,bool u=false){abi(p,n,u?"i32@0:8^S16^S24":"i32@0:8^s16^s24");int16_t lo=0,hi=0;ok(((int(*)(id,SEL,int16_t*,int16_t*))objc_msgSend)(p,sel_registerName(n),&lo,&hi),n);return @[@(lo),@(hi)];}
static int integer(id value,const char*why){need([value isKindOfClass:NSNumber.class]&&CFGetTypeID((CFTypeRef)value)!=CFBooleanGetTypeID()&&[value doubleValue]==[value intValue],why);return [value intValue];}
static int inRange(id v,NSArray*r,const char*why){int n=integer(v,why);need(n>=[r[0] intValue]&&n<=[r[1] intValue],why);return n;}
static NSDictionary* colors(){return @{@"off":@0,@"yellow":@1,@"orange":@2,@"red":@3,@"magenta":@4,@"blue":@5,@"cyan":@6,@"green":@7,@"yellow-green":@8};}
static NSDictionary* capabilities(id p){
 bool supported=enabled(p,"isMonochroCreatorEnabled");
 if(!supported)return @{@"available":@NO,@"reason":@"native monochrome creator unsupported on this raw procedure"};
 abi(p,"rangeOfMonochroCreatorRadialMin:radialMax:rotationMin:rotationMax:","i48@0:8^S16^S24^S32^S40");uint16_t a=0,b=0,c=0,d=0;
 ok(((int(*)(id,SEL,uint16_t*,uint16_t*,uint16_t*,uint16_t*))objc_msgSend)(p,sel_registerName("rangeOfMonochroCreatorRadialMin:radialMax:rotationMin:rotationMax:"),&a,&b,&c,&d),"native MONO filter range");
 need(a==0&&b==3&&c==0&&d==8,"unsupported MONO filter enum range");
 NSMutableArray*states=[NSMutableArray arrayWithObject:@{@"color":@"off",@"strength":@0}];
 for(NSString*n in @[@"red",@"orange",@"yellow",@"yellow-green",@"green",@"cyan",@"blue",@"magenta"])for(int s=1;s<=3;s++)[states addObject:@{@"color":n,@"strength":@(s)}];
 return @{@"available":@YES,@"kind":@"stock_pen_f_mono",@"mode":@"manual",@"native_finishing_mode":@2,@"native_parameter_mode":@2,@"native_contrast_sharpness_mode":@1,@"creative_shading_rng":@{@"policy":@"fixed_native_startup_seed_per_pass",@"restores_prior":@YES,@"not_camera_profile_field":@YES,@"private_api_status":@"recovered_undocumented_C2_D2_ABI_with_live_symbol_and_layout_guards"},@"filter_color_rotation":colors(),@"canonical_filter_states":states,@"grain":@[@"off"],@"native_grain_off":@0,@"toning":@[@"neutral"],@"native_neutral_toning":@2,@"shading":range(p,"rangeOfShadingCreatorShadingMin:shadingMax:"),@"contrast":range(p,"rangeOfContrastMinValue:maxValue:"),@"sharpness":range(p,"rangeOfSharpnessMinValue:maxValue:"),@"native_grain_range":range(p,"rangeOfMonochroCreatorGraininessMin:graininessMax:",true),@"native_toning_range":range(p,"rangeOfMonochroCreatorColorToneMin:colorToneMax:"),@"processing":@"installed native MonochroCreator; no wrapper grayscale or saturation conversion",@"per_photo_fields":@[@"white_balance_mode",@"custom_wb2",@"exposure_bias"],@"color_profile_state_reset":@"manual COLOR/HSL channels disabled and neutralized before MONO activation"};
}
static NSDictionary* apply(id p,NSDictionary*profile){
 need([profile isKindOfClass:NSDictionary.class]&&[profile[@"kind"] isEqual:@"stock_pen_f_mono"]&&[profile[@"mode"] isEqual:@"manual"],"explicit manual native MONO profile required");
 NSDictionary*cap=capabilities(p);need([cap[@"available"] boolValue],"native MONO unsupported");
 need([profile[@"grain"] isEqual:@"off"],"MONO initially supports explicit grain off only");need([profile[@"toning"] isEqual:@"neutral"],"MONO initially supports explicit neutral toning only");
 NSDictionary*f=profile[@"color_filter"];need([f isKindOfClass:NSDictionary.class],"MONO color_filter required");NSString*color=f[@"color"];NSNumber*rot=colors()[color];need(rot!=nil,"unknown MONO filter color");int strength=integer(f[@"strength"],"MONO filter integer strength required");need(strength>=0&&strength<=3,"MONO filter strength must be0..3");
 // Canonical off: any strength0 or color off becomes rotation0/radial0.
 uint16_t rotation=(!strength||[color isEqual:@"off"])?0:rot.unsignedShortValue;uint16_t radial=rotation?strength:0;
 int contrast=inRange(profile[@"contrast"],cap[@"contrast"],"MONO contrast out of native range");int sharp=inRange(profile[@"sharpness"],cap[@"sharpness"],"MONO sharpness out of native range");int shade=inRange(profile[@"shading"],cap[@"shading"],"MONO shading out of native range");need(enabled(p,"isShadingCreatorEnabled"),"creative MONO shading unsupported");
 // Do not let inherited/overlaid COLOR profile channels reactivate another family.
 NSArray*zero=@[@0,@0,@0,@0,@0,@0,@0,@0,@0,@0,@0,@0];
 if(enabled(p,"isColorCreator2Enabled")){abi(p,"setColorCreator2Mode:radialArray:","i28@0:8S16@20");ok(((int(*)(id,SEL,uint16_t,id))objc_msgSend)(p,sel_registerName("setColorCreator2Mode:radialArray:"),0,zero),"disable COLOR creator");}
 for(const char*n:{"setColorProfileMode:hueArray:","setColorProfileMode:lumArray:"}){if([p respondsToSelector:sel_registerName(n)]){abi(p,n,"i28@0:8S16@20");ok(((int(*)(id,SEL,uint16_t,id))objc_msgSend)(p,sel_registerName(n),0,zero),"disable HSL creator");}}
 setScalar(p,"setArtFilterMode:",0);setScalar(p,"setFinishingMode:",2);
 abi(p,"setMonochroCreatorColFilMode:radialValue:rotationValue:","i28@0:8S16S20S24");ok(((int(*)(id,SEL,uint16_t,uint16_t,uint16_t))objc_msgSend)(p,sel_registerName("setMonochroCreatorColFilMode:radialValue:rotationValue:"),2,radial,rotation),"MONO color filter");
 setPair(p,"setMonochroCreatorGraininessMode:graininess:",2,0,true);setPair(p,"setMonochroCreatorColorToneMode:colorTone:",2,2);setPair(p,"setShadingCreatorMode:shading:",2,shade);
 for(const char*n:{"setContrastMode:value:adjust:","setSharpnessMode:value:adjust:"}){abi(p,n,"i28@0:8S16s20s24");ok(((int(*)(id,SEL,uint16_t,int16_t,int16_t))objc_msgSend)(p,sel_registerName(n),1,strstr(n,"Contrast")?contrast:sharp,0),n);}
 return @{@"kind":@"stock_pen_f_mono",@"mode":@"manual",@"color_filter":@{@"color":rotation?color:@"off",@"strength":@(radial),@"native_rotation":@(rotation)},@"grain":@"off",@"toning":@"neutral",@"shading":@(shade),@"contrast":@(contrast),@"sharpness":@(sharp)};
}
// Independent current parameter interface; these are actual native values after
// setToRawDecoder, not a copy of requested JSON or default* ORF getters.
static NSDictionary* readback(void*decoder){void*p=nullptr;int rc=((int(*)(void*,void**))slot(decoder,52,"GetDC11RawDisplayParameters"))(decoder,&p);need(!rc&&p,"native MONO current parameter interface unavailable");struct Guard{void*p;~Guard(){if(p)((unsigned(*)(void*))(*(void***)p)[4])(p);}}guard{p};{
 NSMutableDictionary*out=[NSMutableDictionary dictionaryWithDictionary:@{@"interface":@"IOlyDC11DisplayParameters",@"get_parameters_status":@(rc)}];
 auto scalar=[&](NSString*k,int i,const char*n){uint16_t v=0;int r=((int(*)(void*,uint16_t*))slot(p,i,n))(p,&v);out[k]=@{@"status":@(r),@"value":@(v)};};
 auto pair=[&](NSString*k,int i,const char*n,bool u){uint16_t mode=0;int16_t value=0;int r=((int(*)(void*,uint16_t*,int16_t*))slot(p,i,n))(p,&mode,&value);out[k]=@{@"status":@(r),@"mode":@(mode),@"value":@(u?(int)(uint16_t)value:(int)value)};};
 auto triple=[&](NSString*k,int i,const char*n){uint16_t mode=0;int16_t value=0,adjust=0;int r=((int(*)(void*,uint16_t*,int16_t*,int16_t*))slot(p,i,n))(p,&mode,&value,&adjust);out[k]=@{@"status":@(r),@"mode":@(mode),@"value":@(value),@"adjust":@(adjust)};};
 triple(@"contrast",43,"GetContrastEPt");triple(@"sharpness",47,"GetSharpnessEPt");scalar(@"white_balance_mode",10,"GetWhiteBalanceMode");
 uint16_t kelvin=0;int16_t ab=0,gm=0;int wb=((int(*)(void*,uint16_t*,int16_t*,int16_t*))slot(p,21,"GetCustomColorTemperature2"))(p,&kelvin,&ab,&gm);out[@"custom_wb2"]=@{@"status":@(wb),@"kelvin":@(kelvin),@"ab_adjust":@(ab),@"gm_adjust":@(gm)};
 int numerator=0,denominator=0;int exp=((int(*)(void*,int*,int*))slot(p,7,"GetExposureBiasEPi"))(p,&numerator,&denominator);out[@"exposure_bias"]=@{@"status":@(exp),@"numerator":@(numerator),@"denominator":@(denominator)};
 uint16_t tone=0;int16_t high=0,low=0,mid=0;int tr=((int(*)(void*,uint16_t*,int16_t*,int16_t*))slot(p,102,"GetToneControlEPt"))(p,&tone,&high,&low);out[@"tone_control"]=@{@"status":@(tr),@"mode":@(tone),@"bright":@(high),@"dark":@(low)};
 if(((bool(*)(void*))slot(p,126,"IsMiddToneControlEnabled"))(p)){tr=((int(*)(void*,uint16_t*,int16_t*,int16_t*,int16_t*))slot(p,127,"GetMiddToneControl"))(p,&tone,&high,&mid,&low);out[@"tone_control_with_mid"]=@{@"status":@(tr),@"mode":@(tone),@"bright":@(high),@"dark":@(low),@"mid":@(mid)};}
 scalar(@"finishing_mode",36,"GetFinishingMode");uint16_t mode=0,radial=0,rotation=0;int r=((int(*)(void*,uint16_t*,uint16_t*,uint16_t*))slot(p,114,"GetMonochroCreator"))(p,&mode,&radial,&rotation);NSString*color=@"unknown";for(NSString*n in colors())if([colors()[n] unsignedShortValue]==rotation)color=n;
 out[@"monochrome"]=@{@"status":@(r),@"mode":@(mode),@"radial":@(radial),@"rotation":@(rotation),@"filter_color":color,@"strength":@(radial)};
 pair(@"grain",117,"GetMonochroCreatorGraininess",true);pair(@"legacy_monochro_shading",120,"GetMonochroCreatorShadingValue",false);pair(@"toning",123,"GetMonochroCreatorColorTone",false);pair(@"creative_shading",131,"GetShadingCreatorValue",false);
 out[@"active_processing_family"]=([out[@"finishing_mode"][@"status"] intValue]==0&&mode==2)?@"native_monochrome_profile":@"other_or_inherited";
 return out;
 }}
static void verify(NSDictionary*expected,NSDictionary*actual){
 need([actual[@"active_processing_family"] isEqual:@"native_monochrome_profile"],"MONO family not active in native current parameters");
 NSDictionary*f=actual[@"finishing_mode"],*m=actual[@"monochrome"];
 need([f[@"status"] intValue]==0&&[f[@"value"] intValue]==2,"MONO base finishing readback mismatch");
 need([m[@"status"] intValue]==0&&[m[@"mode"] intValue]==2&&[m[@"radial"] intValue]==[expected[@"color_filter"][@"strength"] intValue]&&[m[@"rotation"] intValue]==[expected[@"color_filter"][@"native_rotation"] intValue],"MONO filter readback mismatch");
 for(NSString*k in @[@"contrast",@"sharpness"]){NSDictionary*r=actual[k];need([r[@"status"] intValue]==0&&[r[@"mode"] intValue]==1&&[r[@"value"] intValue]==[expected[k] intValue]&&[r[@"adjust"] intValue]==0,"MONO contrast/sharpness readback mismatch");}
 for(NSString*k in @[@"grain",@"toning",@"creative_shading",@"legacy_monochro_shading"]){NSDictionary*r=actual[k];int v=[k isEqual:@"grain"]?0:[k isEqual:@"toning"]?2:[expected[@"shading"] intValue];need([r[@"status"] intValue]==0&&[r[@"mode"] intValue]==2&&[r[@"value"] intValue]==v,"MONO explicit control readback mismatch");}
}

struct ShadingContext {id procedure;int value;unsigned rotation=0;NSDictionary*report=nil;};
// Installed desktop creative-shading stage. RAW display parameters alone only
// preserve this value for metadata; OMOlyMuseExtend executes its pixel effect.
// Input is developed/oriented/MFTS-corrected native YCbCr, before RGB conversion.
static void* shadingStage(void*input,void*opaque){
 ShadingContext&c=*(ShadingContext*)opaque;need(c.value>=-5&&c.value<=5,"MONO creative shading out of range");
 if(!c.value){((unsigned(*)(void*))slot(input,3,"AddRef"))(input);c.report=@{@"applied":@NO,@"value":@0,@"reason":@"explicit neutral creative shading"};return input;}
 NSString*path=@"/Applications/OM Workspace.app/Contents/Frameworks/OMOlyMuseExtend.framework/OMOlyMuseExtend";void*lib=dlopen(path.fileSystemRepresentation,RTLD_NOW|RTLD_GLOBAL);need(lib,"installed creative shading framework unavailable");
 auto createFilter=(int(*)(void**,unsigned))dlsym(lib,"OlyMuseExtendCreateShadingCreatorInstance");auto createParam=(int(*)(const void*,void**))dlsym(lib,"OlyMuseExtendCreateInstance");void*iid=dlsym(lib,"IID_IOlyIPFilterRawArtShadingCreatorDC11Parameter");need(createFilter&&createParam&&iid,"installed creative shading factories unavailable");
 NSMutableDictionary*rng=[NSMutableDictionary dictionary];omw_native_rng::Scope rngScope(rng);
 omw_desktop::Ref filter,param,output;ok(createFilter(&filter.p,60),"native RAW creative shading filter");ok(createParam(iid,&param.p),"native creative shading parameters");need(filter.p&&param.p,"native creative shading factory returned null");
 abi(c.procedure,"rawEngineVersion","I16@0:8");unsigned version=((unsigned(*)(id,SEL))objc_msgSend)(c.procedure,sel_registerName("rawEngineVersion"));
 id over=((id(*)(id,SEL))objc_msgSend)(c.procedure,sel_registerName("overProcessArtFilterParameters"));need(over&&[over respondsToSelector:sel_registerName("data")],"creative shading requires RAW over-process data after development");
 NSData*data=((id(*)(id,SEL))objc_msgSend)(over,sel_registerName("data"));need([data isKindOfClass:NSData.class]&&data.length,"native RAW over-process data unavailable for creative shading");
 int mode=enabled(c.procedure,"isShadingCreatorEnabled")?0:1;need(mode==0,"only genuine RAW creative shading is exposed");
 ok(((int(*)(void*,int))slot(param.p,18,"SetFilterMode"))(param.p,mode),"RAW creative shading mode");ok(((int(*)(void*,int16_t))slot(param.p,16,"SetShadingValue"))(param.p,c.value),"RAW creative shading value");
 int16_t actual=0;ok(((int(*)(void*,int16_t*))slot(param.p,17,"GetShadingValue"))(param.p,&actual),"creative shading value readback");int actualMode=((int(*)(void*))slot(param.p,19,"GetFilterMode"))(param.p);need(actual==c.value&&actualMode==mode,"creative shading parameter readback mismatch");
 ok(((int(*)(void*,const void*,size_t,unsigned))slot(filter.p,30,"SetArtOverProcessParameter"))(filter.p,data.bytes,data.length,version),"attach native RAW over-process data");
 ok(((int(*)(void*,void*))slot(filter.p,24,"SetFilterParameter"))(filter.p,param.p),"attach creative shading parameters");
 omw_desktop::filter(filter,input,output);
 c.report=@{@"applied":@YES,@"implementation":@"installed OMOlyMuseExtend RAW ShadingCreator",@"filter_id":@60,@"image_rotation":@(c.rotation),@"filter_mode":@(actualMode),@"value":@(actual),@"raw_engine_version":@(version),@"over_process_bytes":@(data.length),@"rng_control":rng,@"stage":@"after native orientation/MFTS, before YCbCrToRGB and output resize"};return output.detach();
}

}
