#pragma once
// File-only profile metadata reader. No camera/session/USB objects are created.
// Uses the same Olive app-property interface as Workspace's profile loader.
@interface NSObject (OMProfileMetadata)
- (id)initWithPath:(NSString*)path;
- (BOOL)getAppPropComponents:(void**)out;
@end
static NSDictionary* profileMetadata(NSString*path){
NSString*root=@"/Applications/OM Workspace.app";
NSDictionary*app=[NSDictionary dictionaryWithContentsOfFile:[root stringByAppendingPathComponent:@"Contents/Info.plist"]];
need(dlopen([[root stringByAppendingPathComponent:@"Contents/Frameworks/CMOlyExifInfoUtilities.framework/CMOlyExifInfoUtilities"] fileSystemRepresentation],RTLD_NOW|RTLD_GLOBAL),"native profile metadata framework");
Class exifClass=objc_getClass("CMExifInfo");need(exifClass,"native profile metadata class unavailable");
id exif=[[exifClass alloc] initWithPath:path];need(exif,"cannot open image metadata");
void*components=nullptr;need([exif getAppPropComponents:&components]&&components,"image has no native Olympus development profile metadata");
omw_desktop::Ref owned(components);
NSMutableDictionary*r=[NSMutableDictionary dictionaryWithDictionary:@{@"schema":@"omrender-profile/1",@"workspace_version":app[@"CFBundleVersion"]?:@"unknown",@"path":path,@"native_parser":@"CMExifInfo / Olive app-property components",@"hardware_operations":@NO,@"hsl_jpeg_transfer_supported":@NO,@"camera_write_performed":@NO}];
uint16_t finishing=0;int rc=((int(*)(void*,uint16_t*))slot(components,34,"GetFinishingMode"))(components,&finishing);
r[@"finishing_mode"]=@{@"status":@(rc),@"value":@(finishing)};
bool colorMode=!rc&&finishing<=18&&((1U<<finishing)&0x20e00U);
auto triple=[&](NSString*k,int i,const char*n){int16_t v=0,lo=0,hi=0;int x=((int(*)(void*,int16_t*,int16_t*,int16_t*))slot(components,i,n))(components,&v,&lo,&hi);r[k]=@{@"status":@(x),@"value":@(v),@"min":@(lo),@"max":@(hi)};};
triple(@"contrast",22,"GetContrast");triple(@"sharpness",24,"GetSharpness");triple(@"midtone_metadata",68,"GetMidToneControl");
auto array=[&](NSString*k,int i,const char*n){void*a=nullptr;int16_t lo=0,hi=0;int status=((int(*)(void*,void**,int16_t*,int16_t*))slot(components,i,n))(components,&a,&lo,&hi);omw_desktop::Ref ownedArray(a);NSMutableArray*values=[NSMutableArray array];if(!status&&a){unsigned count=((unsigned(*)(void*))slot(a,7,"GetSize"))(a);need(count<=100,"invalid native profile array size");const int16_t*data=((const int16_t*(*)(void*))slot(a,8,"GetData"))(a);need(data||!count,"invalid native profile array storage");for(unsigned j=0;j<count;j++)[values addObject:@(data[j])];}r[k]=@{@"status":@(status),@"values":values,@"min":@(lo),@"max":@(hi)};};
array(@"saturation",70,"GetColorCreater2Point");array(@"hue",80,"GetColorCreater2PointHue");array(@"luminance",82,"GetColorCreater2PointLum");
int16_t bright=0,brightMin=0,brightMax=0,dark=0,darkMin=0,darkMax=0;
rc=((int(*)(void*,int16_t*,int16_t*,int16_t*,int16_t*,int16_t*,int16_t*))slot(components,66,"GetToneControl"))(components,&bright,&brightMin,&brightMax,&dark,&darkMin,&darkMax);
r[@"highlight_shadow_metadata"]=@{@"status":@(rc),@"bright":@(bright),@"bright_min":@(brightMin),@"bright_max":@(brightMax),@"dark":@(dark),@"dark_min":@(darkMin),@"dark_max":@(darkMax)};
int16_t shading=0;rc=((int(*)(void*,int16_t*))slot(components,76,"GetMonochroCreatorShadingValue"))(components,&shading);r[@"shading"]=@{@"status":@(rc),@"value":@(shading)};
bool stock=colorMode&&[r[@"saturation"][@"status"] intValue]==0&&[r[@"saturation"][@"values"] count]==12;
for(NSNumber*n in r[@"saturation"][@"values"])stock=stock&&abs(n.intValue)<=5;
for(NSString*k in @[@"hue",@"luminance"]){NSDictionary*a=r[k];int status=[a[@"status"] intValue];if(status==0){stock=stock&&[a[@"values"] count]==12;for(NSNumber*n in a[@"values"])stock=stock&&n.intValue==0;}else{stock=stock&&(status==(int)0x80000008);}}
r[@"color_profile_finishing_mode"]=@(colorMode);r[@"stock_wheel_transport_eligible"]=@(stock);
r[@"transfer_note"]=@"File metadata only; camera bank/slot compatibility and hardware transfer are separate. WB/exposure are render settings, not part of the profile upload. JPEG loading does not carry H/L and resets them on the documented HSL firmware.";
NSDictionary*loader=nativeProfileDetails(path);r[@"native_camera_loader"]=loader;
bool scalarRanges=true;for(NSString*k in @[@"contrast",@"sharpness"]){NSDictionary*v=r[k];scalarRanges=scalarRanges&&[v[@"status"] intValue]==0&&[v[@"value"] intValue]>=[v[@"min"] intValue]&&[v[@"value"] intValue]<=[v[@"max"] intValue];}
NSDictionary*camera=loader[@"parameters"];
bool agreement=[loader[@"finishing_mode"] isEqual:r[@"finishing_mode"][@"value"]]&&[camera[@"saturation"] isEqual:r[@"saturation"][@"values"]];
for(NSString*k in @[@"contrast",@"sharpness"])agreement=agreement&&[camera[k] isEqual:r[k][@"value"]];
agreement=agreement&&[camera[@"toneControlBright"] isEqual:r[@"highlight_shadow_metadata"][@"bright"]]&&[camera[@"toneControlDark"] isEqual:r[@"highlight_shadow_metadata"][@"dark"]]&&[camera[@"toneControlMid"] isEqual:r[@"midtone_metadata"][@"value"]]&&[camera[@"shadingValue"] isEqual:r[@"shading"][@"value"]];
scalarRanges=scalarRanges&&[r[@"highlight_shadow_metadata"][@"status"] intValue]==0&&[r[@"midtone_metadata"][@"status"] intValue]==0&&[r[@"shading"][@"status"] intValue]==0;
r[@"native_readers_agree"]=@(agreement);
r[@"stock_profile_transport_eligible"]=@(stock&&scalarRanges&&agreement&&[loader[@"accepted"] boolValue]&&[loader[@"has_finishing_mode"] boolValue]&&![loader[@"would_adjust_parameters"] boolValue]);
augmentMonoProfileMetadata(r,components,loader);
[exif release];return r;
}
static int printProfileMetadata(NSString*path){@try{try{NSDictionary*r=profileMetadata(path);NSData*b=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted|NSJSONWritingSortedKeys error:nil];need(b,"profile JSON");fwrite(b.bytes,1,b.length,stdout);fputc('\n',stdout);return 0;}catch(const std::exception&e){fprintf(stderr,"omrender: %s\n",e.what());return 1;}}@catch(NSException*x){fprintf(stderr,"omrender: %s\n",x.description.UTF8String);return 1;}}
