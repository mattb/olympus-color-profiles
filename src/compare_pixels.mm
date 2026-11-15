#include <algorithm>

#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <CommonCrypto/CommonDigest.h>
#include <cmath>
#include <cstdint>
static NSString* hash(NSData*d){if(!d)return (id)[NSNull null];unsigned char md[CC_SHA256_DIGEST_LENGTH];CC_SHA256(d.bytes,(CC_LONG)d.length,md);NSMutableString*s=[NSMutableString string];for(unsigned char c:md)[s appendFormat:@"%02x",c];return s;}
struct Decoded{NSBitmapImageRep*rep;NSMutableData*canonical;NSDictionary*meta;};
static Decoded decode(NSString*path){
 NSData*data=[NSData dataWithContentsOfFile:path];if(!data)@throw [NSException exceptionWithName:@"Input" reason:[@"Cannot read " stringByAppendingString:path] userInfo:nil];
 NSBitmapImageRep*r=[[NSBitmapImageRep alloc]initWithData:data];if(!r)@throw [NSException exceptionWithName:@"Decode" reason:@"NSBitmapImageRep could not decode input" userInfo:nil];
 NSInteger w=r.pixelsWide,h=r.pixelsHigh,bits=r.bitsPerSample,spp=r.samplesPerPixel;
 if((bits!=8&&bits!=16)||(r.bitmapFormat&NSBitmapFormatFloatingPointSamples))@throw [NSException exceptionWithName:@"Unsupported" reason:@"Only integer8/16 samples supported" userInfo:nil];
 unsigned char*planes[5]={};[r getBitmapDataPlanes:planes];
 NSMutableData*out=[NSMutableData dataWithLength:w*h*spp*(bits/8)];unsigned char*dst=(unsigned char*)out.mutableBytes;
 bool little=(r.bitmapFormat&NSBitmapFormatSixteenBitLittleEndian)!=0;
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
 if(!(r.bitmapFormat&NSBitmapFormatSixteenBitBigEndian))little=true;
#endif
 size_t o=0;
 bool packed=r.isPlanar||r.bitsPerPixel==spp*bits;
 for(NSInteger y=0;y<h;y++)for(NSInteger x=0;x<w;x++){
  NSUInteger values[16]={};if(!packed){if(spp>16)@throw [NSException exceptionWithName:@"Unsupported" reason:@"Too many samples" userInfo:nil];[r getPixel:values atX:x y:y];}
  for(NSInteger c=0;c<spp;c++){
   if(!packed){unsigned v=(unsigned)values[c];dst[o++]=v&255;if(bits==16)dst[o++]=(v>>8)&255;continue;}
   unsigned char*p=planes[r.isPlanar?c:0]+y*r.bytesPerRow+(r.isPlanar?x:x*spp+c)*(bits/8);
   if(bits==8)dst[o++]=*p;else{dst[o++]=p[little?0:1];dst[o++]=p[little?1:0];}
  }
 }
 NSData*icc=[r valueForProperty:NSImageColorSyncProfileData];
 NSDictionary*m=@{@"path":path,@"width":@(w),@"height":@(h),@"bits_per_sample":@(bits),@"samples_per_pixel":@(spp),@"bytes_per_row":@(r.bytesPerRow),@"planar":@(r.isPlanar),@"bitmap_format":@(r.bitmapFormat),@"alpha":@(r.hasAlpha),@"color_space_name":r.colorSpaceName?:@"unknown",@"icc_bytes":@(icc.length),@"icc_sha256":hash(icc),@"decoded_pixel_sha256":hash(out),@"hash_layout":@"row-major, original sample order, no padding, unsigned samples, little-endian16; no color conversion"};
 return {r,out,m};
}
int main(int argc,char**argv){@autoreleasepool{@try{
 if(argc!=3)return 64;Decoded a=decode(@(argv[1])),b=decode(@(argv[2]));NSMutableDictionary*result=[@{@"a":a.meta,@"b":b.meta,@"color_conversion":@"none",@"icc_profiles_equal":@([a.meta[@"icc_sha256"] isEqual:b.meta[@"icc_sha256"]])} mutableCopy];
 bool compatible=a.rep.pixelsWide==b.rep.pixelsWide&&a.rep.pixelsHigh==b.rep.pixelsHigh&&a.rep.bitsPerSample==b.rep.bitsPerSample&&a.rep.samplesPerPixel==b.rep.samplesPerPixel;
 result[@"compatible_layout"]=@(compatible);
 if(compatible){unsigned bits=(unsigned)a.rep.bitsPerSample,spp=(unsigned)a.rep.samplesPerPixel;size_t n=a.canonical.length/(bits/8),changed=0,changedPixels=0;long double sa=0,ss=0;unsigned mx=0;auto ap=(const unsigned char*)a.canonical.bytes,bp=(const unsigned char*)b.canonical.bytes;
 for(size_t i=0;i<n;i++){unsigned av=bits==8?ap[i]:ap[i*2]+256*ap[i*2+1],bv=bits==8?bp[i]:bp[i*2]+256*bp[i*2+1];unsigned d=av>bv?av-bv:bv-av;sa+=d;ss+=(long double)d*d;if(d){changed++;mx=std::max(mx,d);}}
 for(size_t px=0;px<n/spp;px++){bool any=false;for(unsigned c=0;c<spp;c++){size_t idx=(px*spp+c)*(bits/8);any|=memcmp(ap+idx,bp+idx,bits/8)!=0;}changedPixels+=any;}
 result[@"comparison"]=@{@"exact_decoded_pixels_equal":@(changed==0),@"sample_count":@(n),@"changed_channels":@(changed),@"changed_pixels":@(changedPixels),@"mae":@((double)(sa/n)),@"rmse":@((double)sqrtl(ss/n)),@"max_absolute_difference":@(mx),@"units":@"integer sample code values",@"color_management_note":@"No color transform performed. ICC differences are reported; equality is meaningful within matching channel semantics."};}
 if(a.rep.pixelsWide==b.rep.pixelsWide&&a.rep.pixelsHigh==b.rep.pixelsHigh&&a.rep.samplesPerPixel==b.rep.samplesPerPixel&&a.rep.bitsPerSample==16&&b.rep.bitsPerSample==8){
  const unsigned char*ap=(const unsigned char*)a.canonical.bytes,*bp=(const unsigned char*)b.canonical.bytes;size_t n=b.canonical.length;NSMutableDictionary*tests=[NSMutableDictionary dictionary];
  for(int mode=0;mode<5;mode++){size_t changed=0;long double sa=0,ss=0;unsigned mx=0;for(size_t k=0;k<n;k++){unsigned v=ap[k*2]+256*ap[k*2+1];unsigned out=mode==0?v>>8:mode==1?v/257:mode==2?(v+128)/257:mode==3?std::min(255u,(v+128)>>8):std::min(255u,(v+255)>>8);unsigned d=out>bp[k]?out-bp[k]:bp[k]-out;changed+=d!=0;sa+=d;ss+=(long double)d*d;mx=std::max(mx,d);}
   NSString*name=@[@"shift8",@"divide257_floor",@"divide257_round",@"shift8_round",@"shift8_ceil"][mode];tests[name]=@{@"changed_channels":@(changed),@"mae":@((double)(sa/n)),@"rmse":@((double)sqrtl(ss/n)),@"max":@(mx)};
  }result[@"quantization_hypotheses"]=tests;
 }
 NSData*j=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted|NSJSONWritingSortedKeys error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return compatible?0:2;
 }@catch(NSException*e){fprintf(stderr,"%s\n",[[e description]UTF8String]);return 1;}}}
