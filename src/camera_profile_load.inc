#pragma once
#include <atomic>
#include <thread>
// The only branch that constructs transport handlers. Invoked solely by explicit
// camera-profile-load, after the running-app/target/output preflight gates.
static id cameraGet(id object,const char*name){return ((id(*)(id,SEL))objc_msgSend)(object,sel(name));}
static unsigned cameraUInt(id object,const char*name){return ((unsigned(*)(id,SEL))objc_msgSend)(object,sel(name));}
static void cameraSet(id object,const char*name,id value){((void(*)(id,SEL,id))objc_msgSend)(object,sel(name),value);}
static BOOL cameraError(BOOL success,NSError**errorPtr,const char*phase){NSError*error=errorPtr?*errorPtr:nil;if(!success){fprintf(stderr,"%s: %s\n",phase,(error.description?:@"native operation failed").UTF8String);throw std::runtime_error(phase);}return success;}
static Class updaterCameraClass(const char*name){Class c=objc_getClass(name);const char*image=c?class_getImageName(c):nullptr;need(c&&image&&strstr(image,"OM Digital Camera Updater.app/Contents/MacOS/OM Digital Camera Updater"),"camera transport class did not come from installed updater");return c;}
struct CameraLoadLifetime {
 id gin=nil,ptp=nil,detector=nil,handler=nil,backup=nil;bool opened=false;
 ~CameraLoadLifetime(){@try{if(opened)((void(*)(id,SEL,unsigned))objc_msgSend)(handler,sel("closeSessionWithCameraNo:"),0);[backup release];[detector release];for(id h : {gin,ptp}){if(h&&[h respondsToSelector:sel("terminateProcess")])((void(*)(id,SEL))objc_msgSend)(h,sel("terminateProcess"));[h release];}stopStandaloneCameraClient();}@catch(NSException*e){fprintf(stderr,"native camera cleanup: %s\n",e.description.UTF8String);}}
};
static int loadCameraProfileWorker(NSString*requestPath){@try{try{
// No transport construction or discovery is allowed while Workspace is running.
NSString*workspaceID=[NSDictionary dictionaryWithContentsOfFile:@"/Applications/OM Workspace.app/Contents/Info.plist"][@"CFBundleIdentifier"];need(workspaceID.length,"installed Workspace identity unavailable");
need([NSRunningApplication runningApplicationsWithBundleIdentifier:workspaceID].count==0,"Quit OM Workspace before camera-profile-load; the CLI will not share or interrupt its session");
NSDictionary*j=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:requestPath] options:0 error:nil];need([j isKindOfClass:NSDictionary.class],"invalid camera load request");
NSString*jpeg=j[@"jpeg"],*serial=j[@"expected_serial"],*backupDir=j[@"backup_dir"],*bank=j[@"bank"];int colorSlot=[j[@"slot"] intValue];
need([serial isKindOfClass:NSString.class]&&serial.length,"expected camera serial required");
NSDictionary*metadata=profileMetadata(jpeg);NSString*family=validatedProfileLoadFamily(j,metadata);BOOL mono=[family isEqual:@"mono"];
unsigned bankMask=[@{@"current":@1,@"c1":@2,@"c2":@4,@"c3":@8,@"c4":@16}[bank] unsignedIntValue];need(bankMask&&colorSlot>=1&&colorSlot<=3,"explicit camera bank and profile slot required");
NSFileManager*fm=NSFileManager.defaultManager;need(![fm fileExistsAtPath:backupDir],"backup directory must be new");
need([fm createDirectoryAtPath:backupDir withIntermediateDirectories:NO attributes:nil error:nil],"cannot create camera backup directory");
NSMutableDictionary*destination=[NSMutableDictionary dictionaryWithDictionary:@{@"bank":bank,@"profile_family":family,@"profile_slot":@(colorSlot)}];destination[mono?@"mono_slot":@"color_slot"]=@(colorSlot);
NSMutableDictionary*report=[NSMutableDictionary dictionaryWithDictionary:@{@"schema":@"omrender-camera-load/1",@"hardware_operations":@YES,@"uploaded":@NO,@"backup_directory":backupDir,@"jpeg":jpeg,@"profile_family":family,@"destination":destination,@"hsl_jpeg_transfer_supported":@NO,@"discovery_may_change_usb_mode":@YES,@"updater_version":@"2.8.5",@"workspace_version":@"2.5.0.2",@"hsl_firmware_effect":mono?@"MONO payload contains no COLOR sector or H/L setting records":@"Stock JPEG import resets destination hue/lightness on the documented HSL firmware"}];
CameraLoadLifetime life;NSError*error=nil;bool writeStarted=false;int result=1;
@try{try{
configureStandaloneCameraClient();fprintf(stderr,"initializing native camera transports\n");
life.gin=[[updaterCameraClass("OlyDCComGinHandler") alloc] init];life.ptp=[[updaterCameraClass("OlyDCComPTPHandlerCCClient") alloc] init];
need(life.gin&&life.ptp,"native camera handlers could not initialize");fprintf(stderr,"native camera transports initialized\n");if(cameraClientBootstrapInfo)report[@"helper_bootstrap"]=cameraClientBootstrapInfo;
life.detector=[[updaterCameraClass("OlyDCFWUpDetectCameraThread") alloc] init];need(life.detector,"native detector could not initialize");
cameraSet(life.detector,"setGinHandler:",life.gin);cameraSet(life.detector,"setPtpHandler:",life.ptp);
((void(*)(id,SEL,BOOL))objc_msgSend)(life.detector,sel("setEnableSubThread:"),YES);
((void(*)(id,SEL,BOOL))objc_msgSend)(life.detector,sel("setEnableChangeOLPTP:"),YES);
((void(*)(id,SEL,double))objc_msgSend)(life.detector,sel("setScanTimeout:"),5.0);
((void(*)(id,SEL))objc_msgSend)(life.detector,sel("startDetectingCamera"));
NSDate*deadline=[NSDate dateWithTimeIntervalSinceNow:25.0];
while(((int(*)(id,SEL))objc_msgSend)(life.detector,sel("threadCondition"))!=3){if([deadline timeIntervalSinceNow]<=0){((void(*)(id,SEL))objc_msgSend)(life.detector,sel("stopDetectingCamera"));throw std::runtime_error("native camera discovery timed out before profile write");}[NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.02]];}
error=cameraGet(life.detector,"detectionError");cameraError(error==nil,&error,"camera discovery");
unsigned storage=cameraUInt(life.detector,"numOfStorageDevices"),mtp=cameraUInt(life.detector,"numOfMTPDevices");
fprintf(stderr,"native camera detection storage=%u mtp=%u\n",storage,mtp);
need(storage+mtp==1,"exactly one camera must be connected; refusing ambiguous or absent device");
need((storage==1&&cameraUInt(life.detector,"numOfSupportedStorageDevices")==1)||(mtp==1&&cameraUInt(life.detector,"numOfSupportedMTPDevices")==1),"detected camera is not supported by native updater");
life.handler=cameraGet(life.detector,"detectedHandler");need(life.handler,"native camera detector supplied no handler");
error=nil;cameraError(((BOOL(*)(id,SEL,unsigned,NSError**))objc_msgSend)(life.handler,sel("openSessionWithCameraNo:error:"),0,&error),&error,"open camera session");life.opened=true;
error=nil;NSArray*infos=((id(*)(id,SEL,unsigned,id,NSError**))objc_msgSend)(life.handler,sel("deviceInfoWithCameraNo:invocation:error:"),0,nil,&error);
need([infos isKindOfClass:NSArray.class],"native camera identity list unavailable");
id body=((id(*)(id,SEL,int,id))objc_msgSend)((id)updaterCameraClass("OlyDCComDeviceInfo"),sel("deviceInfoWithDeviceType:fromArray:"),1,infos);need(body,"native camera body identity unavailable");
NSDictionary*target=@{@"model":cameraGet(body,"modelName")?:@"",@"firmware":cameraGet(body,"devicePublicVersion")?:@"",@"serial":cameraGet(body,"serialNo")?:@""};report[@"target"]=target;
need([target[@"serial"] isEqual:serial],"camera serial mismatch; no profile write attempted");need([target[@"model"] isEqual:@"PEN-F"],"only PEN-F profile loading is exposed");
NSArray*ops=cameraGet(body,"supportedOperationsArray");need([ops containsObject:@0x970b],"camera firmware does not advertise profile settings support");
unsigned selectable=0,type=0,functions=0;
error=nil;cameraError(((BOOL(*)(id,SEL,unsigned,unsigned*,unsigned*,NSError**))objc_msgSend)(life.handler,sel("targetMySetModeWithCameraNo:mode:type:error:"),0,&selectable,&type,&error),&error,"query camera banks");
need((selectable&bankMask)==bankMask,"requested bank is not selectable on this camera");
error=nil;cameraError(((BOOL(*)(id,SEL,unsigned,unsigned*,NSError**))objc_msgSend)(life.handler,sel("checkMySetFunctionWithCameraNo:function:error:"),0,&functions,&error),&error,"query profile-family capability");need(functions&(mono?2U:1U),mono?"native camera does not permit MONO profile loading":"native camera does not permit COLOR profile loading");
BOOL dial=YES;if([ops containsObject:@0x970e])dial=((BOOL(*)(id,SEL,unsigned))objc_msgSend)(life.handler,sel("isDialmysetNeedWithCameraNo:"),0);
unsigned profiles=3;if([ops containsObject:@0x970d]){unsigned reported=0;if(((BOOL(*)(id,SEL,unsigned,unsigned*,NSError**))objc_msgSend)(life.handler,sel("getNumOfExtMysetWithCameraNo:numOfProfiles:error:"),0,&reported,nullptr))profiles=reported;}
need((unsigned)colorSlot<=profiles,"requested profile slot is unavailable");
report[@"capabilities"]=@{@"selectable_banks":@(selectable),@"myset_type":@(type),@"functions":@(functions),@"dial_myset_supported":@(dial),@"number_of_profiles":@(profiles)};
life.backup=[[updaterCameraClass("OlyDCFWUpMySet") alloc] init];cameraSet(life.backup,"setComHandler:",life.handler);
if(![j[@"skip_backup"] boolValue]){NSString*backupPath=[backupDir stringByAppendingPathComponent:@"before.set"];error=nil;
cameraError(((BOOL(*)(id,SEL,id,unsigned,NSError**))objc_msgSend)(life.backup,sel("downloadMySetFileToPath:withTargetMode:error:"),backupPath,selectable&0x7ff,&error),&error,"back up camera settings");need([fm fileExistsAtPath:backupPath],"native backup did not create a file; refusing profile write");report[@"backup"]=backupPath;report[@"backup_scope"]=@"All selectable native setting banks; physical restore coverage is not yet validated";}else{report[@"backup_skipped"]=@YES;}
NSString*csv=nativeProfileCSV(jpeg,target,bank,colorSlot,dial,family);NSData*payload=[csv dataUsingEncoding:NSUTF8StringEncoding];
NSString*csvPath=[backupDir stringByAppendingPathComponent:@"profile.csv"];need([payload writeToFile:csvPath options:NSDataWritingWithoutOverwriting error:nil],"cannot save native upload payload");report[@"payload"]=csvPath;
// MONO isolation evidence is a read-only state capture, not a native .set backup.
// Require a before state so the caller can prove all COLOR recipes were preserved.
if(mono){error=nil;NSData*before=((id(*)(id,SEL,unsigned,unsigned,unsigned,NSError**))objc_msgSend)(life.backup,sel("downloadMySetWithTargetMode:itemIndex:totalCount:error:"),bankMask,0,1,&error);cameraError(before!=nil&&before.length>0,&error,"capture pre-upload settings for COLOR preservation");NSString*beforePath=[backupDir stringByAppendingPathComponent:@"before-readback.bin"];need([before writeToFile:beforePath options:NSDataWritingWithoutOverwriting error:nil],"cannot save pre-upload settings readback");report[@"before_readback"]=beforePath;report[@"before_readback_purpose"]=@"Read-only native settings state for COLOR1/2/3 and unrelated-setting preservation checks; no .set backup or restore performed by this capture";}

error=nil;NSArray*verifyInfos=((id(*)(id,SEL,unsigned,id,NSError**))objc_msgSend)(life.handler,sel("deviceInfoWithCameraNo:invocation:error:"),0,nil,&error);
id verifyBody=((id(*)(id,SEL,int,id))objc_msgSend)((id)updaterCameraClass("OlyDCComDeviceInfo"),sel("deviceInfoWithDeviceType:fromArray:"),1,verifyInfos);
need(verifyBody&&[cameraGet(verifyBody,"serialNo") isEqual:serial]&&[cameraGet(verifyBody,"modelName") isEqual:@"PEN-F"],"camera identity changed before upload; refusing profile write");
writeStarted=true;report[@"camera_write_may_have_occurred"]=@YES;report[@"phase"]=@"upload_started";
[[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil] writeToFile:[backupDir stringByAppendingPathComponent:@"progress.json"] options:NSDataWritingAtomic error:nil];
error=nil;cameraError(((BOOL(*)(id,SEL,id,BOOL,NSError**))objc_msgSend)(life.backup,sel("uploadMySetData:skipColdStart:error:"),payload,YES,&error),&error,"native profile upload");report[@"uploaded"]=@YES;report[@"phase"]=@"upload_completed_readback_pending";
[[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nil] writeToFile:[backupDir stringByAppendingPathComponent:@"progress.json"] options:NSDataWritingAtomic error:nil];
error=nil;NSData*after=((id(*)(id,SEL,unsigned,unsigned,unsigned,NSError**))objc_msgSend)(life.backup,sel("downloadMySetWithTargetMode:itemIndex:totalCount:error:"),bankMask,0,1,&error);cameraError(after!=nil,&error,"download camera settings for readback");
NSString*readback=[backupDir stringByAppendingPathComponent:@"after.bin"];need([after writeToFile:readback options:NSDataWritingWithoutOverwriting error:nil],"cannot save camera readback");report[@"readback"]=readback;report[@"native_upload_completed"]=@YES;report[@"recipe_readback_verified"]=@NO;result=0;
}catch(const std::exception&e){report[@"error"]=@(e.what());report[@"camera_write_may_have_occurred"]=@(writeStarted);}}
@catch(NSException*e){report[@"error"]=e.description;report[@"camera_write_may_have_occurred"]=@(writeStarted);}
NSData*data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted|NSJSONWritingSortedKeys error:nil];[data writeToFile:[backupDir stringByAppendingPathComponent:@"native-result.json"] options:NSDataWritingWithoutOverwriting error:nil];
if(result)fprintf(stderr,"omrender camera load: %s; inspect %s\n",[report[@"error"] UTF8String],backupDir.UTF8String);return result;
}catch(const std::exception&e){fprintf(stderr,"omrender camera load: %s\n",e.what());return 1;}}@catch(NSException*e){fprintf(stderr,"omrender camera load: %s\n",e.description.UTF8String);return 1;}}

// Keep the main run loop available for native ImageCapture/helper callbacks.
static int loadCameraProfile(NSString*request){
std::atomic<bool>done{false};int result=1;
std::thread worker([&](){@autoreleasepool{result=loadCameraProfileWorker(request);done.store(true);}});
while(!done.load())[NSRunLoop.currentRunLoop runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.02]];
worker.join();return result;
}
