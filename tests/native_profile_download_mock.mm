#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#include <dlfcn.h>
@interface NSObject(MySetRead)
-(void)setComHandler:(id)h;
-(NSData*)downloadMySetWithTargetMode:(unsigned)m itemIndex:(unsigned)i totalCount:(unsigned)c error:(NSError**)e;
@end
@interface ReadMock:NSObject
@property(retain) NSData*payload;
@property(retain) NSMutableArray*events;
@end
@implementation ReadMock
@synthesize payload,events;
-(id)init{if((self=[super init]))events=[NSMutableArray new];return self;}
-(BOOL)prepareReadMySetWithCameraNo:(unsigned)c mode:(unsigned)m type:(unsigned)t error:(NSError**)e{[events addObject:@{@"call":@"prepare",@"camera":@(c),@"mode":@(m),@"type":@(t)}];return YES;}
-(BOOL)checkReadyReadMySetWithCameraNo:(unsigned)c statusCode:(unsigned*)s error:(NSError**)e{*s=2;[events addObject:@{@"call":@"checkReady",@"status":@2}];return YES;}
-(BOOL)mySetDataSizeWithCameraNo:(unsigned)c dataType:(unsigned)t dataSize:(unsigned*)s error:(NSError**)e{*s=(unsigned)payload.length;[events addObject:@{@"call":@"dataSize",@"type":@(t),@"size":@(*s)}];return YES;}
-(BOOL)downloadMySetWithCameraNo:(unsigned)c dataType:(unsigned)t offset:(unsigned)o size:(unsigned)n receivedData:(NSData**)d readSize:(unsigned*)r error:(NSError**)e{*d=[payload subdataWithRange:NSMakeRange(o,n)];*r=n;[events addObject:@{@"call":@"download",@"type":@(t),@"offset":@(o),@"size":@(n)}];return YES;}
@end
int main(){@autoreleasepool{@try{void*h=dlopen("/Applications/OM Workspace.app/Contents/Helpers/OM Digital Camera Updater.app/Contents/MacOS/OM Digital Camera Updater",RTLD_NOW|RTLD_GLOBAL);if(!h){puts(dlerror());return 1;}ReadMock*m=[ReadMock new];NSMutableData*p=[NSMutableData dataWithLength:140003];uint8_t*b=(uint8_t*)p.mutableBytes;for(unsigned i=0;i<p.length;i++)b[i]=(i*17+23)%256;m.payload=p;id n=[[objc_getClass("OlyDCFWUpMySet")alloc]init];[n setComHandler:m];NSError*e=nil;NSData*r=[n downloadMySetWithTargetMode:4 itemIndex:0 totalCount:1 error:&e];NSDictionary*j=@{@"native_class":@"OlyDCFWUpMySet",@"transport":@"ReadMock:NSObject",@"hardware_operations":@NO,@"returned_class":NSStringFromClass(r.class)?:@"nil",@"input_size":@(p.length),@"output_size":@(r.length),@"byte_identical":@([p isEqual:r]),@"error":e.description?:@"none",@"events":m.events};NSData*d=[NSJSONSerialization dataWithJSONObject:j options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");return 0;}@catch(NSException*e){fprintf(stderr,"%s\n",e.description.UTF8String);return 2;}}}
