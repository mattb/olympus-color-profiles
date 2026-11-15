// Recovered private ABI for OM Workspace 2.5.0.2, Apple Silicon.
// Loads installed components; this source contains no proprietary code.
#import <AppKit/AppKit.h>
#import <objc/message.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <initializer_list>
#include <stdexcept>
#include <cstdio>
#include <chrono>
#include <unistd.h>

@interface NSObject (OMPrivate)
+ (BOOL)initializeLibraries;
- (id)initWithFileAtPath:(NSString*)p;
- (BOOL)rawDecoder:(void**)p;
- (id)rawProcedure;
- (BOOL)imgProperty:(void**)p;
- (id)initWithImgProperty:(void*)p;
- (id)readFromFile:(NSString*)p;
+ (void)applyParameters:(id)p toRawProc:(id)r exifInfo:(id)e;
- (void)setColorProfileData:(NSData*)d;
- (BOOL)isMiddToneControlEnabled;
- (int)setToneControlMode:(uint16_t)m brightValue:(int16_t)b darkValue:(int16_t)d middValue:(int16_t)v;
- (int)setColorCreator2Mode:(uint16_t)m radialArray:(NSArray*)a;
- (int)colorCreator2Mode:(uint16_t*)m radialArray:(NSArray**)a;
- (int)setColorProfileMode:(uint16_t)m hueArray:(NSArray*)a;
- (int)setColorProfileMode:(uint16_t)m lumArray:(NSArray*)a;
- (int)colorProfileMode:(uint16_t*)m hueArray:(NSArray**)a;
- (int)colorProfileMode:(uint16_t*)m lumArray:(NSArray**)a;
- (void)setToRawDecoder:(void*)p;
- (BOOL)isColorCreator2Enabled;
- (int)setExposureBiasNumerator:(int)n denominator:(int)d;
- (int)setCustomColorTemperature2:(uint16_t)k abAdjust:(int16_t)a gmAdjust:(int16_t)g;
- (int)setWhiteBalanceMode:(uint16_t)m;
- (int)setColorSpaceMode:(uint16_t)m;
- (int)setFinishingMode:(uint16_t)m;
- (int)setToneMode:(uint16_t)m;
- (int)setNoiseFilterSettingMode:(uint16_t)m;
- (int)setContrastMode:(uint16_t)m value:(int16_t)v adjust:(int16_t)a;
- (int)setSharpnessMode:(uint16_t)m value:(int16_t)v adjust:(int16_t)a;
- (int)setSaturationMode:(uint16_t)m value:(int16_t)v adjust:(int16_t)a;
- (int)setToneControlMode:(uint16_t)m brightValue:(int16_t)b darkValue:(int16_t)d;
- (id)initWithOlyImage:(void*)p;
- (BOOL)rotateWithAngle:(int)a;
- (BOOL)resizeImageWithSize:(NSSize)s quality:(NSInteger)q;
- (NSBitmapImageRep*)createBitmapImageRep;
- (NSData*)colorProfileData;
- (int)redComponentPosition;
- (int)greenComponentPosition;
- (int)blueComponentPosition;
@end
static void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
static void ok(int rc,const char*s){if(rc){fprintf(stderr,"%s status=0x%08x\n",s,rc);throw std::runtime_error(s);}}
static SEL sel(const char*s){return sel_registerName(s);}
static void* slot(void*p,int i,const char*name){void*f=(*(void***)p)[i];Dl_info d{};need(dladdr(f,&d)&&d.dli_sname&&strstr(d.dli_sname,name),"private ABI mismatch");return f;}
#include "parameter_state.inc"
#include "gpu_backend.inc"
#include "desktop_pipeline.inc"
#include "mono_profile.inc"
static NSDictionary* profileMetadata(NSString*path);
#include "camera_profile.inc"
#include "profile_metadata.inc"
#include "camera_client_bootstrap.inc"
#include "camera_profile_load.inc"
static unsigned info(void*p,int i,const char*n){unsigned v=0;ok(((int(*)(void*,unsigned*))slot(p,i,n))(p,&v),n);return v;}
static NSArray* sectors(id a,int limit){need([a isKindOfClass:NSArray.class]&&[a count]==12,"exactly twelve sector values required");for(id n in a)need([n isKindOfClass:NSNumber.class]&&[n doubleValue]==[n intValue]&&abs([n intValue])<=limit,"invalid sector value");return a;}
static NSDictionary* scalarState(id p,const char*name){uint16_t m=0;int rc=((int(*)(id,SEL,uint16_t*))objc_msgSend)(p,sel(name),&m);return @{@"status":@(rc),@"value":@(m)};}
static NSDictionary* tripleState(id p,const char*name){uint16_t m=0;int16_t a=0,b=0;int rc=((int(*)(id,SEL,uint16_t*,int16_t*,int16_t*))objc_msgSend)(p,sel(name),&m,&a,&b);return @{@"status":@(rc),@"mode":@(m),@"value":@(a),@"adjust":@(b)};}
// Observational provenance: startup allocator policy is supplied by the launcher.
// These controls affect reclamation, not rendering parameters or camera metadata.
static NSDictionary* allocatorEnvironment(){NSDictionary*e=NSProcessInfo.processInfo.environment;return @{@"MallocAggressiveMadvise":e[@"MallocAggressiveMadvise"]?:@"",@"MallocLargeCache":e[@"MallocLargeCache"]?:@""};}
static NSString* invokedNativeExecutable(){NSString*p=NSProcessInfo.processInfo.arguments.firstObject?:@"";if(!p.isAbsolutePath)p=[NSFileManager.defaultManager.currentDirectoryPath stringByAppendingPathComponent:p];return p.stringByStandardizingPath.stringByResolvingSymlinksInPath;}
using NativeClock=std::chrono::steady_clock;
static double elapsedMs(NativeClock::time_point a,NativeClock::time_point b){return std::chrono::duration<double,std::milli>(b-a).count();}
static bool librariesInitialized=false;
static OMWGPUBackend*sharedGPU=nullptr;
static NSString*gpuUnavailableReason=nil;
static void configureCPUStartup(){id a=((id(*)(id,SEL))objc_msgSend)((id)objc_getClass("OlyGPUAppContext"),sel_registerName("sharedInstance"));((void(*)(id,SEL,id))objc_msgSend)(a,sel_registerName("setSetupRawProcedureBlock:"),^(id p){((void(*)(id,SEL,BOOL))objc_msgSend)(p,sel_registerName("setUseGPU:"),NO);});}

static int renderJob(NSString*input,NSString*sp,NSString*output,bool profileJPEG=false){@autoreleasepool {@try{try{
auto jobStart=NativeClock::now();NSFileManager*fm=NSFileManager.defaultManager;
need(![fm fileExistsAtPath:output]&&![fm fileExistsAtPath:[output stringByAppendingString:@".json"]],"output exists; refusing overwrite");
NSDictionary*s=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:sp] options:0 error:nil];need([s isKindOfClass:NSDictionary.class],"invalid settings JSON");
need([s[@"schema"] isEqual:@"omrender/1"],"unknown schema");need([s[@"inherit"] isEqual:@"orf_shooting_parameters"],"declare inheritance explicitly");
NSString*kind=s[@"profile"][@"kind"];BOOL hsl=[kind isEqual:@"firmware_hsl_research"],mono=[kind isEqual:@"stock_pen_f_mono"];need(!profileJPEG||!hsl,"JPEG camera profile transfer supports stock saturation only; HSL metadata transport is not supported");need(mono||hsl||[kind isEqual:@"stock_pen_f"],"unknown profile kind");
NSArray*sat=mono?nil:sectors(s[@"profile"][@"saturation"],hsl?7:5);NSArray*hue=nil,*lum=nil;
if(hsl){hue=sectors(s[@"profile"][@"hue"],7);lum=sectors(s[@"profile"][@"luminance"],7);}
need([s[@"profile"][@"mode"] isEqual:@"manual"],"profile mode must be manual");
NSString*root=@"/Applications/OM Workspace.app";
NSDictionary*app=[NSDictionary dictionaryWithContentsOfFile:[root stringByAppendingPathComponent:@"Contents/Info.plist"]];
need([app[@"CFBundleVersion"] isKindOfClass:NSString.class],"installed app version metadata unavailable");
auto settingsEnd=NativeClock::now();
if(!librariesInitialized){
for(auto n:{"OlyBase","OlyImageProc_arm","OMRawDevControl"}){NSString*p=[NSString stringWithFormat:@"%@/Contents/Frameworks/%s.framework/%s",root,n,n];void*h=dlopen(p.fileSystemRepresentation,RTLD_NOW|RTLD_GLOBAL);if(!h){fprintf(stderr,"%s\n",dlerror());throw std::runtime_error("framework load");}}
for(auto n:{"OlyIP2_Initialize","OlyIPIF_Initialize","OlyIPRE_Initialize"}){auto f=(int(*)())dlsym(RTLD_DEFAULT,n);need(f,"missing initializer");ok(f(),n);}
need([objc_getClass("OlyRawProcedure") initializeLibraries],"raw engine initializers failed");
omw_native_rng::initialize();librariesInitialized=true;}
NSString*requestedBackend=s[@"backend"]?:@"auto";need([@[@"auto",@"cpu",@"gpu"] containsObject:requestedBackend],"backend must be auto, cpu or gpu");
BOOL wantGPU=![requestedBackend isEqual:@"cpu"];
if(wantGPU&&!sharedGPU&&!gpuUnavailableReason){try{sharedGPU=new OMWGPUBackend(initializeGPU(root));[sharedGPU->metadata retain];}catch(const std::exception&e){gpuUnavailableReason=[@(e.what()) copy];}}
if([requestedBackend isEqual:@"gpu"]&&gpuUnavailableReason)throw std::runtime_error(gpuUnavailableReason.UTF8String);
BOOL usingGPU=wantGPU&&sharedGPU; if(usingGPU)configureRawProcedureStartup(*sharedGPU);else configureCPUStartup();
auto initEnd=NativeClock::now();
id reader=[[objc_getClass("OlyRawFileReader") alloc] initWithFileAtPath:input];need(reader,"open ORF failed");void*d=nullptr;need([reader rawDecoder:&d]&&d,"no raw decoder");
// Explicit desktop path. Never USB/camera development.
uint16_t instructions=[s[@"decode_instructions"] unsignedShortValue];need(s[@"decode_instructions"]!=nil,"explicit decode_instructions required");
ok(((int(*)(void*,uint16_t))slot(d,81,"SetDecodeInstructions"))(d,instructions),"decode instructions");
need(!((bool(*)(void*))slot(d,85,"GetUseCameraToDevelop"))(d),"camera development prohibited");
id proc=[reader rawProcedure];
if(usingGPU){configureRawDecoderGPU(d,*sharedGPU);void*rawProc=nullptr;ok(((int(*)(void*,void**))slot(d,50,"GetDC11RawProc"))(d,&rawProc),"GPU raw procedure");need(rawProc,"GPU raw procedure absent");Dl_info impl{};dladdr((*(void***)rawProc)[0],&impl);BOOL peony=impl.dli_fname&&strstr(impl.dli_fname,"OlyPeony_arm.framework");((unsigned(*)(void*))slot(rawProc,4,"Release"))(rawProc);need(peony,"GPU requested but native procedure is not Peony");}

NSDictionary*oesDecoded=@{};
if(s[@"oes_file"]){NSString*oes=s[@"oes_file"];if(!oes.isAbsolutePath)oes=[[sp stringByDeletingLastPathComponent] stringByAppendingPathComponent:oes];
NSString*batch=[root stringByAppendingPathComponent:@"Contents/Frameworks/OMBatchProcess.framework/OMBatchProcess"];need(dlopen(batch.fileSystemRepresentation,RTLD_NOW|RTLD_GLOBAL),"OES framework load");
id parser=[[objc_getClass("OMBatchProcessFileDecoder2") alloc] init];oesDecoded=[parser readFromFile:oes];need([oesDecoded[@"cmBatchParams"] isKindOfClass:NSDictionary.class],"OES decode failed");void*property=nullptr;need([reader imgProperty:&property]&&property,"ORF metadata");id exif=[[objc_getClass("CMExifInfo") alloc] initWithImgProperty:property];[objc_getClass("OMRawDevControl") applyParameters:oesDecoded[@"cmBatchParams"] toRawProc:proc exifInfo:exif];((unsigned(*)(void*))slot(property,4,"Release"))(property);[exif release];[parser release];}
if(!mono){need([proc isColorCreator2Enabled],"wheel unsupported");
ok([proc setColorCreator2Mode:2 radialArray:sat],"saturation");
NSArray*zero=@[@0,@0,@0,@0,@0,@0,@0,@0,@0,@0,@0,@0];
// Stock profile explicitly has neutral H/L; hacked-ORF H/L must not leak in.
if(!hsl){hue=zero;lum=zero;}
ok([proc setColorProfileMode:2 hueArray:hue],"hue");ok([proc setColorProfileMode:2 lumArray:lum],"luminance");}
NSDictionary*o=s[@"raw_overrides"]?:@{};
for(NSString*k in o){need(!mono||![@[@"finishing_mode",@"contrast",@"sharpness",@"global_saturation"] containsObject:k],"MONO profile owns family, contrast and sharpness; contradictory raw override");id v=o[k];if([k isEqual:@"exposure_bias"]){ok([proc setExposureBiasNumerator:[v[0] intValue] denominator:[v[1] intValue]],"exposure");}
else if([k isEqual:@"custom_wb2"]){ok([proc setCustomColorTemperature2:[v[0] unsignedShortValue] abAdjust:[v[1] shortValue] gmAdjust:[v[2] shortValue]],"custom WB");}
else if([k isEqual:@"tone_control"]){if([v count]==4){need([v[3] shortValue]==0||[proc isMiddToneControlEnabled],"midtone unsupported on this RAW");ok([proc setToneControlMode:[v[0] unsignedShortValue] brightValue:[v[1] shortValue] darkValue:[v[2] shortValue] middValue:[v[3] shortValue]],"tone control mid");}else ok([proc setToneControlMode:[v[0] unsignedShortValue] brightValue:[v[1] shortValue] darkValue:[v[2] shortValue]],"tone control");}
else if([k isEqual:@"contrast"]||[k isEqual:@"sharpness"]||[k isEqual:@"global_saturation"]){const char*n=[k isEqual:@"contrast"]?"setContrastMode:value:adjust:":[k isEqual:@"sharpness"]?"setSharpnessMode:value:adjust:":"setSaturationMode:value:adjust:";ok(((int(*)(id,SEL,uint16_t,int16_t,int16_t))objc_msgSend)(proc,sel(n),[v[0] unsignedShortValue],[v[1] shortValue],[v[2] shortValue]),n);}
else {NSDictionary*names=@{@"white_balance_mode":@"setWhiteBalanceMode:",@"color_space_mode":@"setColorSpaceMode:",@"finishing_mode":@"setFinishingMode:",@"gradation_mode":@"setToneMode:",@"noise_filter_setting_mode":@"setNoiseFilterSettingMode:"};NSString*n=names[k];need(n!=nil,"unknown raw override");ok(((int(*)(id,SEL,uint16_t))objc_msgSend)(proc,NSSelectorFromString(n),[v unsignedShortValue]),n.UTF8String);}}
NSDictionary*monoCanonical=mono?omw_mono::apply(proc,s[@"profile"]):@{};
uint16_t mode=0;NSArray*read=nil;if(!mono){ok([proc colorCreator2Mode:&mode radialArray:&read],"wheel readback");need(mode==2&&[read isEqual:sat],"wheel readback mismatch");}
NSMutableDictionary*state=[NSMutableDictionary dictionary];if(!mono){state[@"saturation"]=read;state[@"profile_mode"]=@(mode);}

for(auto n:{"colorSpaceMode:","finishingMode:","toneMode:","noiseFilterSettingMode:","artFilterMode:"})state[@(n)]=scalarState(proc,n);
for(auto n:{"contrastMode:value:adjust:","sharpnessMode:value:adjust:","saturationMode:value:adjust:","toneControlMode:brightValue:darkValue:"})state[@(n)]=tripleState(proc,n);
[proc setToRawDecoder:d];
NSDictionary*actual=displayState(d);NSDictionary*monoActual=mono?omw_mono::readback(d):@{};if(mono){omw_mono::verify(monoCanonical,monoActual);state[@"monochrome"]=monoActual;}
uint16_t actualInstructions=0;ok(((int(*)(void*,uint16_t*))slot(d,82,"GetDecodeInstructions"))(d,&actualInstructions),"instruction readback");need(actualInstructions==instructions,"decode instruction mismatch");
void*gpuContext=nullptr;int gpuStatus=((int(*)(void*,void**))slot(d,63,"GetGPUContext"))(d,&gpuContext);BOOL hasGPU=gpuContext!=nullptr;if(gpuContext)((unsigned(*)(void*))slot(gpuContext,4,"Release"))(gpuContext);

if(!mono)for(NSString*k in @[@"saturation",@"hue",@"luminance"]){NSArray*expected=[k isEqual:@"saturation"]?sat:[k isEqual:@"hue"]?hue:lum;NSDictionary*r=actual[k];need([r[@"status"] intValue]==0&&[r[@"mode"] intValue]==2&&[r[@"values"] isEqual:expected],"native profile parameter readback mismatch");state[k]=r;}
need([actual[@"available"] boolValue],"current parameter readback unavailable for this camera engine");
auto preparationEnd=NativeClock::now();
unsigned bits=[s[@"output"][@"bits"] unsignedIntValue];need(bits==8||bits==16,"bits must be 8 or 16");void*image=nullptr;
int rotation=[s[@"output"][@"rotate"] intValue];need(rotation==0||rotation==90||rotation==180||rotation==270,"invalid rotation");
int sensorWidth=0,sensorHeight=0;ok(((int(*)(void*,int*,unsigned,unsigned,unsigned))slot(d,6,"GetImageWidth"))(d,&sensorWidth,0,1,1),"sensor width");ok(((int(*)(void*,int*,unsigned,unsigned,unsigned))slot(d,7,"GetImageHeight"))(d,&sensorHeight,0,1,1),"sensor height");
omw_mono::ShadingContext monoShade{proc,mono?[monoCanonical[@"shading"] intValue]:0,(unsigned)rotation};
if(usingGPU||mono){void*property=nullptr;need([reader imgProperty:&property]&&property,"native source property");omw_desktop::Ref propertyRef(property);image=omw_desktop::develop(d,property,rotation,usingGPU?sharedGPU->context:nullptr,16,1,true,mono?omw_mono::shadingStage:nullptr,mono?&monoShade:nullptr);}
else{ok(((int(*)(void*,void**,unsigned,unsigned,unsigned,unsigned,bool,unsigned))slot(d,15,"GetImageE"))(d,&image,0,16,3,1,false,0),"full RAW develop");}
if(mono&&[monoCanonical[@"shading"] intValue]!=0){NSDictionary*rng=monoShade.report[@"rng_control"];need([rng[@"prior_seed_restored"] boolValue]&&!rng[@"restore_error"],"native random state restoration failed; refusing output and further batch jobs");}
need(image,"no developed image");auto developmentEnd=NativeClock::now();
unsigned w=info(image,5,"GetWidth"),h=info(image,6,"GetHeight");need(w>1000&&h>1000,"unexpected small image");
id wrapper=[[objc_getClass("OlyImage") alloc] initWithOlyImage:image];need(wrapper,"image wrapper");
if(rotation&&!usingGPU&&!mono)need([wrapper rotateWithAngle:rotation],"rotation");
id size=s[@"output"][@"resize"];if(size){need([size count]==2,"resize width height");need([wrapper resizeImageWithSize:NSMakeSize([size[0] doubleValue],[size[1] doubleValue]) quality:1],"resize");}
unsigned color=[state[@"colorSpaceMode:"][@"value"] unsignedIntValue];
if(color==0){NSDictionary*def=scalarState(proc,"defaultColorSpaceMode:");need([def[@"status"] intValue]==0,"default color-space readback failed");state[@"defaultColorSpaceMode:"]=def;color=[def[@"value"] unsignedIntValue];}
need(color==1||color==2,"unknown resolved output color space");state[@"resolved_color_space_mode"]=@(color);
NSString*iccPath=[root stringByAppendingPathComponent:color==2?@"Contents/Resources/Profiles/AdobeRGB1998.icc":@"Contents/Resources/Profiles/sRGBColorSpace.icm"];NSData*icc=[NSData dataWithContentsOfFile:iccPath];need(icc.length>0,"installed ICC missing");[wrapper setColorProfileData:icc];
NSBitmapImageRep*bm=[wrapper createBitmapImageRep];need(bm,"bitmap");
auto postprocessingEnd=NativeClock::now();
if(profileJPEG){
need(bits==8,"profile JPEG requires output.bits=8");
NSString*batch=[root stringByAppendingPathComponent:@"Contents/Frameworks/OMBatchProcess.framework/OMBatchProcess"];need(dlopen(batch.fileSystemRepresentation,RTLD_NOW|RTLD_GLOBAL),"native JPEG writer framework");
Class c=objc_getClass("FileSave");SEL setProc=sel("setRawProc:");SEL save=sel("saveAsExifJpegFromBitmapRep:atSrcPath:atDstPath:jpegQuality:atomically:embedProfile:keepFaceTag:");
Method setter=class_getInstanceMethod(c,setProc),m=class_getInstanceMethod(c,save);
need(setter&&!strcmp(method_getTypeEncoding(setter),"v24@0:8@16")&&m&&!strcmp(method_getTypeEncoding(m),"s56@0:8@16@24@32i40B44B48B52"),"unsupported native profile JPEG writer ABI");
id writer=[[c alloc] init];((void(*)(id,SEL,id))objc_msgSend)(writer,setProc,proc);
NSString*tmp=[[output stringByDeletingLastPathComponent] stringByAppendingPathComponent:[NSString stringWithFormat:@".omrender-%@.jpg",NSUUID.UUID.UUIDString]];
int16_t status=((int16_t(*)(id,SEL,id,id,id,int,BOOL,BOOL,BOOL))objc_msgSend)(writer,save,bm,input,tmp,100,YES,YES,NO);[writer release];
if(status){[fm removeItemAtPath:tmp error:nil];ok(status,"native profile JPEG export");}
need([fm moveItemAtPath:tmp toPath:output error:nil],"native JPEG final move (destination must not exist)");
bm=[[[NSBitmapImageRep alloc] initWithData:[NSData dataWithContentsOfFile:output]] autorelease];need(bm&&bm.bitsPerSample==8,"native JPEG verification");
}
else if(bits==16){NSData*tiff=[bm representationUsingType:NSBitmapImageFileTypeTIFF properties:@{NSImageCompressionMethod:@1}];need(tiff&&[tiff writeToFile:output options:NSDataWritingWithoutOverwriting error:nil],"TIFF output");}
else{
// Workspace develops16, then uses its own FileSave8 quantizer. The generic
// OlyIP2_ConvertTo8Bits shortcut is native but does not match desktop exports.
NSString*batch=[root stringByAppendingPathComponent:@"Contents/Frameworks/OMBatchProcess.framework/OMBatchProcess"];need(dlopen(batch.fileSystemRepresentation,RTLD_NOW|RTLD_GLOBAL),"native TIFF8 writer framework");Class c=objc_getClass("FileSave");SEL save=sel_registerName("saveAsTIFFFromBitmapRep:atSrcPath:atDstPath:atomically:embedProfile:bitsPerSample:embedExifIFD:");Method m=class_getInstanceMethod(c,save);need(m&&!strcmp(method_getTypeEncoding(m),"s56@0:8@16@24@32B40B44i48B52"),"unsupported native TIFF8 writer ABI");
id writer=[[c alloc] init];NSString*tmp=[[output stringByDeletingLastPathComponent] stringByAppendingPathComponent:[NSString stringWithFormat:@".omrender-%@.tif",NSUUID.UUID.UUIDString]];
int16_t status=((int16_t(*)(id,SEL,id,id,id,BOOL,BOOL,int,BOOL))objc_msgSend)(writer,save,bm,input,tmp,YES,YES,8,YES);[writer release];
if(status){[fm removeItemAtPath:tmp error:nil];ok(status,"native TIFF8 export");}
need([fm moveItemAtPath:tmp toPath:output error:nil],"native TIFF8 final move (destination must not exist)");
bm=[[[NSBitmapImageRep alloc] initWithData:[NSData dataWithContentsOfFile:output]] autorelease];need(bm&&bm.bitsPerSample==8,"native TIFF8 verification");
}
auto encodeEnd=NativeClock::now();
NSDictionary*timings=@{@"settings_ms":@(elapsedMs(jobStart,settingsEnd)),@"library_init_ms":@(elapsedMs(settingsEnd,initEnd)),@"preparation_ms":@(elapsedMs(initEnd,preparationEnd)),@"development_ms":@(elapsedMs(preparationEnd,developmentEnd)),@"postprocessing_ms":@(elapsedMs(developmentEnd,postprocessingEnd)),@"encode_write_ms":@(elapsedMs(postprocessingEnd,encodeEnd)),@"total_through_tiff_ms":@(elapsedMs(jobStart,encodeEnd))};
NSDictionary*backendReport=@{@"requested":requestedBackend,@"used":usingGPU?@"gpu":@"cpu",@"pipeline":mono?(usingGPU?@"native_ycbcr_then_orientation_then_gpu_mfts_then_creative_shading_then_rgb":@"native_ycbcr_then_orientation_then_cpu_mfts_then_creative_shading_then_rgb"):usingGPU?@"native_ycbcr_then_orientation_then_gpu_mfts_then_rgb":@"native_cpu_develop_then_orientation",@"gpu_initialization_error":gpuUnavailableReason?:@"",@"device":usingGPU?sharedGPU->metadata:@{}};
NSString*nativeExecutable=invokedNativeExecutable();
NSDictionary*report=@{@"allocator_environment":allocatorEnvironment(),@"native_executable":nativeExecutable,@"build_dir":nativeExecutable.stringByDeletingLastPathComponent,@"renderer_protocol":@"omrender-native/2",@"output_format":profileJPEG?@"jpeg":@"tiff",@"backend":backendReport,@"process_id":@(getpid()),@"timings":timings,@"settings":s,@"profile_kind":kind,@"profile_canonical":monoCanonical,@"mono_parameters":monoActual,@"mono_creative_shading_stage":mono?(monoShade.report?:@{}):@{},@"settings_precedence":@"ORF inheritance, OES overlay, explicit raw_overrides, then explicit MONO style (when selected)",@"home_directory":NSHomeDirectory(),@"decode_instructions_readback":@(actualInstructions),@"gpu_context_present":@(hasGPU),@"gpu_context_status":@(gpuStatus),@"oes_decoded":oesDecoded,@"current_parameters":actual,@"icc_source":iccPath,@"settings_readback":state,@"input":input,@"app_version":app[@"CFBundleVersion"],@"raw_dimensions":@[@(sensorWidth),@(sensorHeight)],@"output_dimensions":@[@(bm.pixelsWide),@(bm.pixelsHigh)],@"bits":@(bm.bitsPerSample),@"development_bits":@16,@"channels":@(bm.samplesPerPixel),@"bitmap_color_space":bm.colorSpaceName?:@"unknown",@"icc_bytes":@(icc.length),@"channel_positions":@[@([wrapper redComponentPosition]),@([wrapper greenComponentPosition]),@([wrapper blueComponentPosition])],@"camera_development":@NO,@"unlisted_settings":@"inherited from ORF shooting parameters; not reset from Workspace UI or user preset"};
need([[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted|NSJSONWritingSortedKeys error:nil] writeToFile:[output stringByAppendingString:@".json"] options:NSDataWritingWithoutOverwriting error:nil],"report output");
fprintf(stdout,"rendered %ux%u to %ldx%ld %ld-bit %s\n",w,h,(long)bm.pixelsWide,(long)bm.pixelsHigh,(long)bm.bitsPerSample,profileJPEG?"JPEG":"TIFF");
// Release COM references before finalizing dependencies; owned process then exits.
((unsigned(*)(void*))slot(image,4,"Release"))(image);((unsigned(*)(void*))slot(d,4,"Release"))(d);[wrapper release];[reader release];return 0;
}catch(const std::exception&e){fprintf(stderr,"omrender: %s\n",e.what());return 1;}}@catch(NSException*e){fprintf(stderr,"omrender: %s\n",e.description.UTF8String);return 1;}}}


static int printMonoCapabilities(NSString*input){@autoreleasepool{@try{try{
 NSString*root=@"/Applications/OM Workspace.app";
 NSDictionary*version=[NSDictionary dictionaryWithContentsOfFile:[root stringByAppendingPathComponent:@"Contents/Info.plist"]];need([version[@"CFBundleVersion"] isKindOfClass:NSString.class],"installed app version metadata unavailable");
 for(auto n:{"OlyBase","OlyImageProc_arm","OMRawDevControl"}){NSString*p=[NSString stringWithFormat:@"%@/Contents/Frameworks/%s.framework/%s",root,n,n];need(dlopen(p.fileSystemRepresentation,RTLD_NOW|RTLD_GLOBAL),"framework load for MONO capabilities");}
 for(auto n:{"OlyIP2_Initialize","OlyIPIF_Initialize","OlyIPRE_Initialize"}){auto f=(int(*)())dlsym(RTLD_DEFAULT,n);need(f,"missing initializer");ok(f(),n);}need([objc_getClass("OlyRawProcedure") initializeLibraries],"raw engine initializers failed");omw_native_rng::initialize();configureCPUStartup();
 id reader=[[objc_getClass("OlyRawFileReader") alloc] initWithFileAtPath:input];need(reader,"open ORF failed");id proc=[reader rawProcedure];need(proc,"no raw procedure");
 NSString*nativeExecutable=invokedNativeExecutable();
 NSDictionary*r=@{@"allocator_environment":allocatorEnvironment(),@"native_executable":nativeExecutable,@"build_dir":nativeExecutable.stringByDeletingLastPathComponent,@"input":input,@"process_id":@(getpid()),@"app_version":version[@"CFBundleVersion"],@"mono_profiles":omw_mono::capabilities(proc),@"hardware_operations":@NO,@"pixels_developed":@NO,@"native_rng_startup_seed":@(omw_native_rng::state.startup)};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted|NSJSONWritingSortedKeys error:nil];need(j,"capability JSON");fwrite(j.bytes,1,j.length,stdout);fputc('\n',stdout);[reader release];return 0;
 }catch(const std::exception&e){fprintf(stderr,"omrender: %s\n",e.what());return 1;}}@catch(NSException*e){fprintf(stderr,"omrender: %s\n",e.description.UTF8String);return 1;}}}

int main(int argc,char**argv){@autoreleasepool {
if(argc==2&&!strcmp(argv[1],"--capabilities")){puts("{\"renderer_protocol\":\"omrender-native/2\",\"backends\":[\"auto\",\"cpu\",\"gpu\"],\"batch\":true,\"mono_profiles\":true,\"creative_shading_rng\":{\"policy\":\"fixed_native_startup_seed_per_pass\",\"restores_prior\":true,\"not_camera_profile_field\":true,\"private_api_status\":\"recovered_undocumented_native_C2_D2\"},\"camera_profile_load_mono\":true,\"gpu_pipeline\":\"orientation_before_mfts\",\"profile_jpeg\":true,\"profile_info\":true,\"camera_profile_csv\":true,\"camera_profile_load\":\"experimental_limited_hardware_validation\",\"camera_profile_skip_backup\":true}");return 0;}
if(argc==3&&!strcmp(argv[1],"--mono-capabilities"))return printMonoCapabilities(@(argv[2]));
if(argc==3&&!strcmp(argv[1],"--camera-profile-load"))return loadCameraProfile(@(argv[2]));
if(argc==4&&!strcmp(argv[1],"--camera-profile-csv"))return writeProfileCSV(@(argv[2]),@(argv[3]));
if(argc==3&&!strcmp(argv[1],"--profile-info"))return printProfileMetadata(@(argv[2]));
if(argc==5&&!strcmp(argv[1],"--profile-jpeg"))return renderJob(@(argv[2]),@(argv[3]),@(argv[4]),true);
if(argc==4)return renderJob(@(argv[1]),@(argv[2]),@(argv[3]));
if(argc==3&&!strcmp(argv[1],"--batch")){
@try{NSArray*jobs=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:@(argv[2])] options:0 error:nil];
if(![jobs isKindOfClass:NSArray.class]||!jobs.count){fprintf(stderr,"omrender: batch must be a nonempty JSON array\n");return 1;}
for(NSDictionary*j in jobs){if(![j isKindOfClass:NSDictionary.class]||![j[@"input"] isKindOfClass:NSString.class]||![j[@"settings"] isKindOfClass:NSString.class]||![j[@"output"] isKindOfClass:NSString.class])return 1;int rc=renderJob(j[@"input"],j[@"settings"],j[@"output"]);if(rc)return rc;}return 0;
}@catch(NSException*e){fprintf(stderr,"omrender: %s\n",e.description.UTF8String);return 1;}}
fprintf(stderr,"usage: omrender INPUT.ORF SETTINGS.json OUTPUT.tif | --batch MANIFEST.json\n");return 1;
}}
