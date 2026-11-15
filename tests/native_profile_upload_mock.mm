#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <initializer_list>
@interface NSObject(UploadMockAPI)
- (BOOL)loadFromImageFile:(NSString*)p;
- (id)createProfileCSVWithModelName:(NSString*)m firmwareVersion:(NSString*)f serialNo:(NSString*)s profileSet:(int)p mySetTypes:(NSArray*)a;
- (void)setComHandler:(id)h;
- (BOOL)uploadMySetData:(NSData*)d skipColdStart:(BOOL)skip error:(NSError**)e;
@end
@interface MockHandler:NSObject
@property(retain) NSMutableArray*events;
@property(retain) NSMutableData*received;
@property(retain) NSString*failure;
@property unsigned polls;
@property unsigned uploadCalls;
@end
@implementation MockHandler
@synthesize events,received,failure,polls,uploadCalls;
- (id)init{if((self=[super init])){events=[NSMutableArray new];received=[NSMutableData new];polls=0;uploadCalls=0;}return self;}
- (BOOL)setMySetSizeWithCameraNo:(unsigned)c requestSize:(unsigned)n actualSize:(unsigned*)out error:(NSError**)e{[events addObject:@{@"call":@"setMySetSize",@"camera_no":@(c),@"request_size":@(n),@"actual_size_pointer_null":@(out==nullptr)}];if([failure isEqual:@"reserve"]){if(e)*e=[NSError errorWithDomain:@"OFFLINE_MOCK" code:901 userInfo:nil];return NO;}if(out)*out=n;return YES;}
- (BOOL)uploadMySetWithCameraNo:(unsigned)c offset:(unsigned)o sendData:(NSData*)d actualSize:(unsigned*)actual error:(NSError**)e{uploadCalls++;[events addObject:@{@"call":@"uploadMySet",@"camera_no":@(c),@"offset":@(o),@"bytes":@(d.length)}];if([failure isEqual:@"upload"]&&uploadCalls==2){if(e)*e=[NSError errorWithDomain:@"OFFLINE_MOCK" code:902 userInfo:nil];return NO;}if(o!=received.length)@throw [NSException exceptionWithName:@"MockOffset" reason:@"offset does not equal received length" userInfo:nil];[received appendData:d];if(actual)*actual=(unsigned)d.length;return YES;}
- (BOOL)checkUploadMySetWithCameraNo:(unsigned)c action:(unsigned)a error:(NSError**)e{[events addObject:@{@"call":@"checkUploadMySet",@"camera_no":@(c),@"action":@(a)}];if([failure isEqual:@"commit"]){if(e)*e=[NSError errorWithDomain:@"OFFLINE_MOCK" code:903 userInfo:nil];return NO;}return YES;}
- (BOOL)checkCompletedUploadMySetWithCameraNo:(unsigned)c statusCode:(unsigned*)s error:(NSError**)e{polls++;unsigned code=[failure hasPrefix:@"status"]?[[failure substringFromIndex:6] intValue]:(polls==1?1:4);if(s)*s=code;[events addObject:@{@"call":@"checkCompletedUploadMySet",@"camera_no":@(c),@"status":@(code)}];return YES;}
- (BOOL)coldStartWithCameraNo:(unsigned)c error:(NSError**)e{[events addObject:@{@"call":@"coldStart",@"camera_no":@(c)}];return YES;}
- (void)dealloc{[events release];[received release];[failure release];[super dealloc];}
@end
static NSDictionary*run(NSData*d,NSString*failure,BOOL skip){MockHandler*h=[MockHandler new];h.failure=failure;id uploader=[[objc_getClass("OlyDCFWUpMySet")alloc]init];[uploader setComHandler:h];NSError*error=nil;BOOL ok=[uploader uploadMySetData:d skipColdStart:skip error:&error];NSDictionary*r=@{@"case":failure?:@"success",@"skip_cold_start":@(skip),@"input_bytes":@(d.length),@"result":@(ok),@"received_equals_input":@([h.received isEqual:d]),@"error_domain":error.domain?:@"none",@"error_code":@(error.code),@"events":[NSArray arrayWithArray:h.events]};[uploader release];[h release];return r;}
int main(int argc,char**argv){@autoreleasepool{@try{if(argc!=2)return 64;void*l=dlopen("/Applications/OM Workspace.app/Contents/Helpers/OM Digital Camera Updater.app/Contents/MacOS/OM Digital Camera Updater",RTLD_NOW|RTLD_GLOBAL);if(!l){puts(dlerror());return 1;}id maker=[[objc_getClass("OlyDCFWUpProfileMaker")alloc]init];if(![maker loadFromImageFile:@(argv[1])])return 2;NSString*csv=[maker createProfileCSVWithModelName:@"PEN-F" firmwareVersion:@"3.1" serialNo:@"OFFLINE-MOCK-NOT-A-CAMERA" profileSet:3 mySetTypes:@[@2,@6]];NSData*small=[csv dataUsingEncoding:NSUTF8StringEncoding];NSMutableData*large=[NSMutableData data];for(int i=0;i<80;i++)[large appendData:small];NSMutableArray*r=[NSMutableArray array];[r addObject:run(small,nil,YES)];[r addObject:run(large,nil,YES)];for(NSString*f in @[@"reserve",@"upload",@"commit",@"status0",@"status2",@"status3",@"status4",@"status5",@"status9"])[r addObject:run(large,f,YES)];[r addObject:run(small,nil,NO)];NSDictionary*out=@{@"native_classes":@[@"OlyDCFWUpProfileMaker",@"OlyDCFWUpMySet"],@"com_handler_class":@"MockHandler (NSObject only)",@"hardware_operations":@NO,@"note":@"Multi-chunk case repeats real native CSV solely to test transport chunking; no camera parses it.",@"results":r};NSData*b=[NSJSONSerialization dataWithJSONObject:out options:NSJSONWritingPrettyPrinted error:nil];fwrite(b.bytes,1,b.length,stdout);fputc('\n',stdout);[maker release];return 0;}@catch(NSException*e){fprintf(stderr,"%s\n",e.description.UTF8String);return 3;}}}
