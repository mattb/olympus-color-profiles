#pragma once
// Adapt only this standalone host's launch of the installed camera helper.
// Preserve native setup, FIFO framing, arguments, and transport implementation.
static IMP originalClientSetup=nullptr,originalTaskLaunchPath=nullptr;
static thread_local bool cameraClientSetupActive=false;
static NSDictionary*cameraClientBootstrapInfo=nil;
static id ownedCameraHelperTask=nil;
static void cameraTaskLaunchPath(id task,SEL command,NSString*path){
 if(cameraClientSetupActive)fprintf(stderr,"camera helper launch path requested=%s task_class=%s\n",path.UTF8String,class_getName(object_getClass(task)));
 if(cameraClientSetupActive&&[path hasSuffix:@"/Contents/Helpers/OlyCCHelper.app/Contents/MacOS/OlyCCHelper"]){
  path=@"/Applications/OM Workspace.app/Contents/Helpers/OM Digital Camera Updater.app/Contents/Helpers/OlyCCHelper.app/Contents/MacOS/OlyCCHelper";
 }
 ((void(*)(id,SEL,id))originalTaskLaunchPath)(task,command,path);
}
static BOOL standaloneCameraClientSetup(id client,SEL command){
 NSString*identifier=[NSString stringWithFormat:@"com.omworkspace-control.camera.%d",getpid()];
 ((void(*)(id,SEL,id))objc_msgSend)(client,sel("setUniqueIdentifier:"),identifier);
 cameraClientSetupActive=true;
 @try{
  BOOL result=((BOOL(*)(id,SEL))originalClientSetup)(client,command);
  id task=((id(*)(id,SEL))objc_msgSend)(client,sel("task"));
  BOOL running=task&&((BOOL(*)(id,SEL))objc_msgSend)(task,sel("isRunning"));
  if(!result||!running)fprintf(stderr,"camera helper launch failed result=%d actual_path=%s\n",result,[[task launchPath] UTF8String]);
  if(!result||!running)@throw [NSException exceptionWithName:@"OMRenderCameraHelperLaunch" reason:@"Installed OlyCCHelper failed to launch; refusing to wait on an unserved FIFO" userInfo:nil];
  [ownedCameraHelperTask release];ownedCameraHelperTask=[task retain];
  [cameraClientBootstrapInfo release];cameraClientBootstrapInfo=[@{@"helper_pid":@(((int(*)(id,SEL))objc_msgSend)(task,sel("processIdentifier"))),@"namespace":identifier,@"fifo_directory":((id(*)(id,SEL))objc_msgSend)(client,sel("FIFODirectory"))?:@"",@"private_home":NSHomeDirectory(),@"installed_helper":@"/Applications/OM Workspace.app/Contents/Helpers/OM Digital Camera Updater.app/Contents/Helpers/OlyCCHelper.app/Contents/MacOS/OlyCCHelper"} copy];
  fprintf(stderr,"camera helper launched pid=%d namespace=%s\n",((int(*)(id,SEL))objc_msgSend)(task,sel("processIdentifier")),identifier.UTF8String);
  return result;
 }@finally{cameraClientSetupActive=false;}
}
static void configureStandaloneCameraClient(){
 if(originalClientSetup)return;
 Class c=objc_getClass("OlyCCClient");Method setup=class_getInstanceMethod(c,sel("setup")),setID=class_getInstanceMethod(c,sel("setUniqueIdentifier:")),task=class_getInstanceMethod(c,sel("task"));
 id taskProbe=[[NSTask alloc] init];Class taskClass=object_getClass(taskProbe);
 Method launch=class_getInstanceMethod(taskClass,sel("setLaunchPath:"));[taskProbe release];
 need(setup&&!strcmp(method_getTypeEncoding(setup),"B16@0:8")&&setID&&!strcmp(method_getTypeEncoding(setID),"v24@0:8@16")&&task&&!strcmp(method_getTypeEncoding(task),"@16@0:8")&&launch&&!strcmp(method_getTypeEncoding(launch),"v24@0:8@16"),"unverified camera helper bootstrap ABI");
 originalTaskLaunchPath=method_setImplementation(launch,(IMP)cameraTaskLaunchPath);
 originalClientSetup=method_setImplementation(setup,(IMP)standaloneCameraClientSetup);
}

static void stopStandaloneCameraClient(){
 // Explicit task ownership survives native handler/shared-client teardown.
 if(ownedCameraHelperTask){if(((BOOL(*)(id,SEL))objc_msgSend)(ownedCameraHelperTask,sel("isRunning")))((void(*)(id,SEL))objc_msgSend)(ownedCameraHelperTask,sel("terminate"));[ownedCameraHelperTask release];ownedCameraHelperTask=nil;}
}
