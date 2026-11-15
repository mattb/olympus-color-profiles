#pragma once
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <mach/machine.h>
#include <mutex>
#include <cstdint>
#include <cstring>
// Native OlyMuse gain dithering uses process-global CRand32 state even when
// simulated grain is off. No installed bytes or loaded code are modified here.
// The private C2/D2 routines operate on OWN 16-byte object storage. D2 publishes
// its seed using the library's own mutex. Address resolution uses live symbols,
// with no fixed offsets, executable copies, disk reads or content pins.
// This header owns one state/epoch in the CLI single translation unit. A future
// multi-TU embedding must centralize this state instead of duplicating it.
namespace omw_native_rng {
struct alignas(8) Object {void*vptr=nullptr;uint32_t seed=0;uint32_t padding=0;};
static_assert(sizeof(Object)==16&&offsetof(Object,seed)==8,"native random object storage");
using Routine=void(*)(Object*);
struct State {Routine construct=nullptr,destroy=nullptr;uint32_t startup=0;bool initialized=false;NSString*image=nil;uintptr_t textBegin=0,textEnd=0;};
static State state;
static std::mutex epochMutex;
struct Symbols {uintptr_t construct=0,destroy=0,constructEnd=0,destroyEnd=0,textBegin=0,textEnd=0;};
static Symbols liveSymbols(const void*anchor){
 Dl_info image{};need(dladdr(anchor,&image)&&image.dli_fbase&&image.dli_fname&&strstr(image.dli_fname,"OlyMuse_arm.framework"),"native random library identity mismatch");
 const mach_header_64*h=(const mach_header_64*)image.dli_fbase;need(h->magic==MH_MAGIC_64&&h->cputype==CPU_TYPE_ARM64&&h->ncmds<4096&&h->sizeofcmds<1024*1024,"unsupported native random Mach-O header");
 const uint8_t*commands=(const uint8_t*)(h+1),*end=commands+h->sizeofcmds,*cursor=commands;const symtab_command*symbols=nullptr;const segment_command_64*linkedit=nullptr;uint64_t textVM=0,textAddress=0,textSize=0;
 for(uint32_t i=0;i<h->ncmds;i++){need(cursor+sizeof(load_command)<=end,"native random load commands truncated");auto*c=(const load_command*)cursor;need(c->cmdsize>=sizeof(load_command)&&cursor+c->cmdsize<=end,"native random load command invalid");
  if(c->cmd==LC_SYMTAB){need(c->cmdsize>=sizeof(symtab_command),"native random symbol command invalid");symbols=(const symtab_command*)c;}
  if(c->cmd==LC_SEGMENT_64){need(c->cmdsize>=sizeof(segment_command_64),"native random segment command invalid");auto*s=(const segment_command_64*)c;
   if(!strncmp(s->segname,"__LINKEDIT",16))linkedit=s;
   if(!strncmp(s->segname,"__TEXT",16)){textVM=s->vmaddr;need(s->nsects<256&&sizeof(*s)+s->nsects*sizeof(section_64)<=c->cmdsize,"native random text sections invalid");auto*sections=(const section_64*)(s+1);for(uint32_t j=0;j<s->nsects;j++)if(!strncmp(sections[j].sectname,"__text",16)){textAddress=sections[j].addr;textSize=sections[j].size;}}
  }cursor+=c->cmdsize;
 }
 need(symbols&&linkedit&&textSize&&symbols->nsyms<1000000,"native random live local symbols unavailable");
 uint64_t nbytes=(uint64_t)symbols->nsyms*sizeof(nlist_64);need(symbols->symoff>=linkedit->fileoff&&symbols->symoff+nbytes<=linkedit->fileoff+linkedit->filesize&&symbols->stroff>=linkedit->fileoff&&(uint64_t)symbols->stroff+symbols->strsize<=linkedit->fileoff+linkedit->filesize,"native random symbol bounds invalid");
 uintptr_t slide=(uintptr_t)h-textVM,base=slide+linkedit->vmaddr-linkedit->fileoff;auto*table=(const nlist_64*)(base+symbols->symoff);auto*strings=(const char*)(base+symbols->stroff);Symbols out;out.textBegin=slide+textAddress;out.textEnd=out.textBegin+textSize;
 const char*ctor="__ZN10OLY_RAWART7CRand32C2Ev",*dtor="__ZN10OLY_RAWART7CRand32D2Ev";
 for(uint32_t i=0;i<symbols->nsyms;i++){auto&n=table[i];if((n.n_type&N_STAB)||(n.n_type&N_TYPE)!=N_SECT||n.n_un.n_strx>=symbols->strsize)continue;const char*name=strings+n.n_un.n_strx;size_t remaining=symbols->strsize-n.n_un.n_strx;if(remaining>strlen(ctor)&&!memcmp(name,ctor,strlen(ctor)+1))out.construct=slide+n.n_value;if(remaining>strlen(dtor)&&!memcmp(name,dtor,strlen(dtor)+1))out.destroy=slide+n.n_value;}
 need(out.construct>=out.textBegin&&out.construct<out.textEnd&&out.destroy>=out.textBegin&&out.destroy<out.textEnd&&!(out.construct&3)&&!(out.destroy&3),"native random routines absent from loaded arm64 text");
 out.constructEnd=out.destroyEnd=out.textEnd;
 for(uint32_t i=0;i<symbols->nsyms;i++){auto&n=table[i];if((n.n_type&N_STAB)||(n.n_type&N_TYPE)!=N_SECT)continue;uintptr_t a=slide+n.n_value;if(a>out.construct&&a<out.constructEnd)out.constructEnd=a;if(a>out.destroy&&a<out.destroyEnd)out.destroyEnd=a;}
 need(out.constructEnd-out.construct<=4096&&out.destroyEnd-out.destroy<=4096,"native random routine bounds unverified");
 // Observed C2: mov x19,x0 then STR Wseed,[x19,#8]. Observed D2:
 // LDR Wseed,[x0,#8]. A layout change fails before any private object calls.
 bool seedStore=false,seedLoad=false;
 for(uintptr_t a=out.construct;a<out.constructEnd;a+=4){uint32_t w;memcpy(&w,(void*)a,4);seedStore|=(w&0xffc003e0U)==0xb9000260U&&((w>>10)&0xfff)==2;}
 for(uintptr_t a=out.destroy;a<out.destroyEnd;a+=4){uint32_t w;memcpy(&w,(void*)a,4);seedLoad|=(w&0xffc003e0U)==0xb9400000U&&((w>>10)&0xfff)==2;}
 need(seedStore&&seedLoad,"native random seed object layout changed");
 Dl_info c{},d{};need(dladdr((void*)out.construct,&c)&&c.dli_sname&&strstr(c.dli_sname,"CRand32C")&&dladdr((void*)out.destroy,&d)&&d.dli_sname&&strstr(d.dli_sname,"CRand32D2"),"native random routine identity mismatch");
 return out;
}
static uint32_t snapshot(){Object object;state.construct(&object);need(object.vptr,"native random constructor returned no vtable");uint32_t seed=object.seed;state.destroy(&object);return seed;}
static void publish(uint32_t seed){Object object;state.construct(&object);need(object.vptr,"native random constructor returned no vtable");object.seed=seed;state.destroy(&object);}
static void initialize(){std::lock_guard<std::mutex>lock(epochMutex);if(state.initialized)return;
 const char*path="/Applications/OM Workspace.app/Contents/Frameworks/OlyMuse_arm.framework/OlyMuse_arm";void*lib=dlopen(path,RTLD_NOW|RTLD_GLOBAL);need(lib,"native random framework load failed");void*anchor=dlsym(lib,"OlyGetRawArtFilter");need(anchor,"native random factory anchor absent");Symbols s=liveSymbols(anchor);state.construct=(Routine)s.construct;state.destroy=(Routine)s.destroy;state.textBegin=s.textBegin;state.textEnd=s.textEnd;state.image=[@(path) copy];state.startup=snapshot();state.initialized=true;
}
// Keep this scope outside the native filter/parameter reference owners, so their
// destruction completes before seed capture/restoration. Every owned Muse pass
// is serialized by epochMutex; no concurrent Muse RNG work is started by the CLI.
struct Scope {
 std::unique_lock<std::mutex>lock;uint32_t prior=0;NSMutableDictionary*report=nil;
 explicit Scope(NSMutableDictionary*r):lock(epochMutex),report([r retain]){bool published=false;@try{try{
  need(state.initialized,"native random startup state was not captured before jobs");prior=snapshot();published=true;publish(state.startup);uint32_t read=snapshot();need(read==state.startup,"native random reset readback mismatch");
  [report addEntriesFromDictionary:@{@"policy":@"fixed_native_startup_seed_per_pass",@"restores_prior":@YES,@"not_camera_profile_field":@YES,@"private_api_status":@"recovered_undocumented_C2_D2_ABI_with_live_symbol_and_layout_guards",@"startup_seed":@(state.startup),@"prior_seed":@(prior),@"seed_before_filter":@(read),@"native_class":@"OLY_RAWART::CRand32",@"constructor":@"C2",@"destructor":@"D2 (non-deleting)",@"object_bytes":@16,@"object_seed_offset":@8,@"resolver":@"live arm64 Mach-O local nlist; text and object-layout guards",@"library":state.image,@"loaded_code_modified":@NO,@"installed_files_modified":@NO}];
 }catch(...){try{if(published)publish(prior);}catch(...){}[report release];report=nil;throw;}}@catch(NSException*e){try{if(published)publish(prior);}catch(...){}[report release];report=nil;@throw;}}

 ~Scope(){@try{try{uint32_t after=snapshot();publish(prior);uint32_t restored=snapshot();report[@"seed_after_filter"]=@(after);report[@"restored_seed"]=@(restored);report[@"prior_seed_restored"]=@(restored==prior);if(restored!=prior)report[@"restore_error"]=@"native random prior-seed verification failed";}catch(const std::exception&e){report[@"restore_error"]=@(e.what());}}@catch(NSException*e){report[@"restore_error"]=e.description;}[report release];}
 Scope(const Scope&)=delete;Scope&operator=(const Scope&)=delete;
};
}
