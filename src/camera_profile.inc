#pragma once
// Load the installed updater's native profile classes without invoking its main,
// window controllers, device discovery, communication initialization or USB APIs.
static Class profileMakerClass(){
static Class cls=Nil;if(cls)return cls;
NSDictionary*info=[NSDictionary dictionaryWithContentsOfFile:@"/Applications/OM Workspace.app/Contents/Helpers/OM Digital Camera Updater.app/Contents/Info.plist"];
need([info[@"CFBundleVersion"] isEqual:@"2.8.5"],"unverified installed camera updater ABI version");
NSString*path=@"/Applications/OM Workspace.app/Contents/Helpers/OM Digital Camera Updater.app/Contents/MacOS/OM Digital Camera Updater";
void*h=dlopen(path.fileSystemRepresentation,RTLD_NOW|RTLD_GLOBAL);if(!h){fprintf(stderr,"%s\n",dlerror());throw std::runtime_error("installed camera profile library could not load");}
cls=objc_getClass("OlyDCFWUpProfileMaker");need(cls,"installed native profile maker unavailable");
need(class_getInstanceMethod(cls,sel("loadFromImageFile:"))&&strcmp(method_getTypeEncoding(class_getInstanceMethod(cls,sel("loadFromImageFile:"))),"B24@0:8@16")==0,"unsupported native profile reader ABI");
return cls;
}
static NSString* nativeProfileFamily(uint16_t mode){
if(mode<=18&&((1U<<mode)&0x20e00U))return @"color";
if(mode<=18&&((1U<<mode)&0x47000U))return @"mono";
return @"unknown";
}
// Pure request/metadata guard. Legacy requests retain COLOR semantics; MONO must
// be explicitly requested and fully validated before any transport constructor.
static NSString* validatedProfileLoadFamily(NSDictionary*request,NSDictionary*metadata){
NSString*family=request[@"profile_family"]?:@"color";
need([@[@"color",@"mono"] containsObject:family],"profile_family must be color or mono");
need([metadata[@"stock_profile_transport_eligible"] boolValue],"JPEG is not an unchanged supported stock profile");
need([metadata[@"profile_family"] isEqual:family],"requested profile family differs from validated JPEG metadata");
return family;
}
static NSDictionary* nativeProfileDetails(NSString*path){
Class c=profileMakerClass();id maker=[[c alloc] init];
BOOL accepted=((BOOL(*)(id,SEL,id))objc_msgSend)(maker,sel("loadFromImageFile:"),path);
BOOL hasMode=((BOOL(*)(id,SEL))objc_msgSend)(maker,sel("hasFinishingMode"));
uint16_t mode=((uint16_t(*)(id,SEL))objc_msgSend)(maker,sel("finishingMode"));
BOOL adjusted=((BOOL(*)(id,SEL))objc_msgSend)(maker,sel("isParameterAdjusted"));
NSMutableDictionary*fields=[NSMutableDictionary dictionary];
for(const char*n:{"contrast","sharpness","toneControlBright","toneControlDark","toneControlMid","shadingValue"})fields[@(n)]=@(((int16_t(*)(id,SEL))objc_msgSend)(maker,sel(n)));
fields[@"saturation"]=((id(*)(id,SEL))objc_msgSend)(maker,sel("colorCreator2Points"))?:@[];
NSString*family=nativeProfileFamily(mode);
if([family isEqual:@"mono"]){
for(const char*n:{"monochroCreatorRadial","monochroCreatorRotation","monochroCreatorGraininess"}){Method m=class_getInstanceMethod(c,sel(n));need(m&&!strcmp(method_getTypeEncoding(m),"S16@0:8"),"unsupported native MONO profile field ABI");fields[@(n)]=@(((uint16_t(*)(id,SEL))objc_msgSend)(maker,sel(n)));}
Method tone=class_getInstanceMethod(c,sel("monochroCreatorColorTone"));need(tone&&!strcmp(method_getTypeEncoding(tone),"s16@0:8"),"unsupported native MONO toning ABI");
fields[@"monochroCreatorColorTone"]=@(((int16_t(*)(id,SEL))objc_msgSend)(maker,sel("monochroCreatorColorTone")));
}
NSDictionary*r=@{@"accepted":@(accepted),@"has_finishing_mode":@(hasMode),@"finishing_mode":@(mode),@"profile_family":family,@"would_adjust_parameters":@(adjusted),@"parameters":fields,@"implementation":@"installed OlyDCFWUpProfileMaker; main/UI/device discovery not invoked"};[maker release];return r;
}
// Call at the end of profileMetadata(), with its existing native references alive.
// COLOR behavior/eligibility stays unchanged. MONO uses its own fields, not S12/H/L.
static void augmentMonoProfileMetadata(NSMutableDictionary*r,void*components,NSDictionary*loader){
uint16_t mode=[r[@"finishing_mode"][@"value"] unsignedShortValue];NSString*family=nativeProfileFamily(mode);r[@"profile_family"]=family;
if(![family isEqual:@"mono"]){r[@"stock_mono_transport_eligible"]=@NO;return;}
uint16_t radial=0,radialMin=0,radialMax=0,rotation=0,rotationMin=0,rotationMax=0,grain=0;int16_t tone=0;
int filterRC=((int(*)(void*,uint16_t*,uint16_t*,uint16_t*,uint16_t*,uint16_t*,uint16_t*))slot(components,72,"GetMonochroCreator"))(components,&radial,&radialMin,&radialMax,&rotation,&rotationMin,&rotationMax);
int grainRC=((int(*)(void*,uint16_t*))slot(components,74,"GetMonochroCreatorGraininess"))(components,&grain);
int toneRC=((int(*)(void*,int16_t*))slot(components,78,"GetMonochroCreatorColorTone"))(components,&tone);
NSArray*colors=@[@"off",@"yellow",@"orange",@"red",@"magenta",@"blue",@"cyan",@"green",@"yellow-green"];
r[@"monochrome_filter"]=@{@"status":@(filterRC),@"strength":@(radial),@"strength_min":@(radialMin),@"strength_max":@(radialMax),@"rotation":@(rotation),@"rotation_min":@(rotationMin),@"rotation_max":@(rotationMax),@"color":rotation<colors.count?colors[rotation]:@"unknown",@"canonical_color":radial==0?@"off":rotation<colors.count?colors[rotation]:@"unknown"};
r[@"monochrome_grain"]=@{@"status":@(grainRC),@"value":@(grain)};r[@"monochrome_toning"]=@{@"status":@(toneRC),@"value":@(tone)};
bool ranges=[r[@"finishing_mode"][@"status"] intValue]==0&&filterRC==0&&grainRC==0&&toneRC==0&&radial<=3&&rotation<=8&&(radial==0||rotation!=0)&&grain==0&&tone==1;
for(NSString*k in @[@"contrast",@"sharpness"]){NSDictionary*v=r[k];ranges=ranges&&[v[@"status"] intValue]==0&&abs([v[@"value"] intValue])<=2;}
NSDictionary*hs=r[@"highlight_shadow_metadata"],*mid=r[@"midtone_metadata"],*shade=r[@"shading"];
ranges=ranges&&[hs[@"status"] intValue]==0&&abs([hs[@"bright"] intValue])<=7&&abs([hs[@"dark"] intValue])<=7&&[mid[@"status"] intValue]==0&&abs([mid[@"value"] intValue])<=7&&[shade[@"status"] intValue]==0&&abs([shade[@"value"] intValue])<=5;
NSDictionary*p=loader[@"parameters"];
bool agreement=[loader[@"finishing_mode"] isEqual:r[@"finishing_mode"][@"value"]]&&[p[@"monochroCreatorRadial"] isEqual:@(radial)]&&[p[@"monochroCreatorRotation"] isEqual:@(rotation)]&&[p[@"monochroCreatorGraininess"] isEqual:@(grain)]&&[p[@"monochroCreatorColorTone"] isEqual:@(tone)];
for(NSString*k in @[@"contrast",@"sharpness"])agreement=agreement&&[p[k] isEqual:r[k][@"value"]];
agreement=agreement&&[p[@"toneControlBright"] isEqual:hs[@"bright"]]&&[p[@"toneControlDark"] isEqual:hs[@"dark"]]&&[p[@"toneControlMid"] isEqual:mid[@"value"]]&&[p[@"shadingValue"] isEqual:shade[@"value"]];
bool eligible=ranges&&agreement&&[loader[@"accepted"] boolValue]&&[loader[@"has_finishing_mode"] boolValue]&&![loader[@"would_adjust_parameters"] boolValue];
r[@"native_readers_agree"]=@(agreement);r[@"stock_mono_transport_eligible"]=@(eligible);r[@"stock_profile_transport_eligible"]=@(eligible);
r[@"transfer_note"]=@"File-only MONO profile: filter, strength, grain, toning, contrast, sharpness, shading and tone. WB/exposure are excluded from reusable transfer. Currently exposed style requires grain off and neutral toning. Current/MONO1 red3 upload/readback and unrelated-setting preservation were verified on one PEN-F; other destinations and persistence remain unvalidated.";
}
// Default COLOR preserves the existing hardware caller's write boundary. Offline
// MONO CSV must opt in with expectedFamily=@"mono" after full metadata validation.
static NSString* nativeProfileCSV(NSString*jpeg,NSDictionary*target,NSString*bank,int colorSlot,BOOL dialSupported,NSString*expectedFamily=@"color"){
Class c=profileMakerClass();id maker=[[c alloc] init];
need(((BOOL(*)(id,SEL,id))objc_msgSend)(maker,sel("loadFromImageFile:"),jpeg),"native camera loader rejected JPEG");
need(!((BOOL(*)(id,SEL))objc_msgSend)(maker,sel("isParameterAdjusted")),"native camera loader would clamp profile parameters");
need(((BOOL(*)(id,SEL))objc_msgSend)(maker,sel("hasFinishingMode")),"native profile has no finishing mode");
uint16_t mode=((uint16_t(*)(id,SEL))objc_msgSend)(maker,sel("finishingMode"));NSString*family=nativeProfileFamily(mode);
need([@[@"color",@"mono"] containsObject:expectedFamily]&&[family isEqual:expectedFamily],"native profile family differs from explicit serializer family");
Method finishSetter=class_getInstanceMethod(c,sel("setFinishingMode:"));need(finishSetter&&!strcmp(method_getTypeEncoding(finishSetter),"v20@0:8S16"),"unsupported native finishing setter ABI");
((void(*)(id,SEL,uint16_t))objc_msgSend)(maker,sel("setFinishingMode:"),[family isEqual:@"mono"]?12:9); // Exact desktop family branch, not raw engine enums.
unsigned mask=[@{@"current":@1,@"c1":@2,@"c2":@4,@"c3":@8,@"c4":@16}[bank] unsignedIntValue];need(mask&&colorSlot>=1&&colorSlot<=3,"explicit supported camera bank and profile slot required");
NSInteger type=((NSInteger(*)(id,SEL,unsigned))objc_msgSend)((id)c,sel("mysetTypeWithBankNumber:"),mask);
NSMutableArray*types=[NSMutableArray arrayWithObject:@(type)];
if(dialSupported){NSInteger dt=((NSInteger(*)(id,SEL,unsigned))objc_msgSend)((id)c,sel("dialMysetTypeWithBankNumber:"),mask);if(dt)[types addObject:@(dt)];}
for(NSString*k in @[@"model",@"firmware",@"serial"]){id value=target[k];need([value isKindOfClass:NSString.class]&&[value length]&&[[value componentsSeparatedByCharactersInSet:[NSCharacterSet characterSetWithCharactersInString:@",\r\n"]] count]==1,"invalid target camera identity");}
SEL create=sel("createProfileCSVWithModelName:firmwareVersion:serialNo:profileSet:mySetTypes:");Method m=class_getInstanceMethod(c,create);need(m&&!strcmp(method_getTypeEncoding(m),"@52@0:8@16@24@32i40@44"),"unsupported native profile CSV ABI");
NSString*csv=((id(*)(id,SEL,id,id,id,int,id))objc_msgSend)(maker,create,target[@"model"],target[@"firmware"],target[@"serial"],colorSlot,types);need(csv.length,"native profile CSV creation failed");[csv retain];[maker release];return [csv autorelease];
}
static int writeProfileCSV(NSString*request,NSString*output){@try{try{
NSDictionary*j=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:request] options:0 error:nil];need([j isKindOfClass:NSDictionary.class],"invalid camera profile CSV request");
NSDictionary*metadata=profileMetadata(j[@"jpeg"]);need([metadata[@"stock_profile_transport_eligible"] boolValue],"not an unchanged stock JPEG profile carrier");
need(j[@"dial_myset_supported"]!=nil,"explicit dial-myset capability required");
NSString*family=metadata[@"profile_family"]?:metadata[@"native_camera_loader"][@"profile_family"];
NSString*csv=nativeProfileCSV(j[@"jpeg"],j[@"target"],j[@"bank"],[j[@"slot"] intValue],[j[@"dial_myset_supported"] boolValue],family);
need([[csv dataUsingEncoding:NSUTF8StringEncoding] writeToFile:output options:NSDataWritingWithoutOverwriting error:nil],"native profile CSV output exists or cannot be written");return 0;
}catch(const std::exception&e){fprintf(stderr,"omrender: %s\n",e.what());return 1;}}@catch(NSException*e){fprintf(stderr,"omrender: %s\n",e.description.UTF8String);return 1;}}
