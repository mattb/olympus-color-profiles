// Private DC11 display-parameter getters observed on OM Workspace 2.5.0.2.
// Include after slot(). Every virtual call verifies its shipped symbol name.
// These are current values, unlike OlyRawProcedure default* getters.
static NSDictionary* displayState(void* decoder) {
    void* p=nullptr;
    int rc=((int(*)(void*,void**))slot(decoder,52,"GetDC11RawDisplayParameters"))(decoder,&p);
    if(rc || !p) return @{@"available":@NO,@"get_display_parameters_status":@(rc),@"reason":@"DC11 current-parameter interface unavailable; other engine layouts not assumed"};
    NSMutableDictionary* out=[NSMutableDictionary dictionaryWithDictionary:@{@"available":@YES,@"interface":@"IOlyDC11DisplayParameters"}];
    auto scalar=[&](NSString*key,int i,const char*name){uint16_t value=0;int r=((int(*)(void*,uint16_t*))slot(p,i,name))(p,&value);out[key]=@{@"status":@(r),@"value":@(value)};};
    auto triple=[&](NSString*key,int i,const char*name){uint16_t mode=0;int16_t a=0,b=0;int r=((int(*)(void*,uint16_t*,int16_t*,int16_t*))slot(p,i,name))(p,&mode,&a,&b);out[key]=@{@"status":@(r),@"mode":@(mode),@"value":@(a),@"adjust":@(b)};};
    int n=0,d=0;rc=((int(*)(void*,int*,int*))slot(p,7,"GetExposureBiasEPi"))(p,&n,&d);
    out[@"exposure_bias"]=@{@"status":@(rc),@"numerator":@(n),@"denominator":@(d)};
    scalar(@"white_balance_mode",10,"GetWhiteBalanceMode");
    uint16_t kelvin=0;int16_t ab=0,gm=0;
    rc=((int(*)(void*,uint16_t*,int16_t*,int16_t*))slot(p,21,"GetCustomColorTemperature2"))(p,&kelvin,&ab,&gm);
    out[@"custom_wb2"]=@{@"status":@(rc),@"kelvin":@(kelvin),@"ab_adjust":@(ab),@"gm_adjust":@(gm)};
    scalar(@"finishing_mode",36,"GetFinishingMode");
    triple(@"contrast",43,"GetContrastEPt");
    triple(@"sharpness",47,"GetSharpnessEPt");
    triple(@"global_saturation",51,"GetSaturationEPt");
    scalar(@"gradation_mode",61,"GetToneMode");
    uint16_t nfmode=0;int16_t nflevel=0;
    rc=((int(*)(void*,uint16_t*,int16_t*))slot(p,64,"GetNoiseFilterEPtPs"))(p,&nfmode,&nflevel);
    out[@"noise_filter"]=@{@"status":@(rc),@"mode":@(nfmode),@"level":@(nflevel)};
    scalar(@"color_space_mode",67,"GetColorSpaceMode");
    scalar(@"false_color_suppression",85,"GetFalseColorSuppression");
    scalar(@"acnode_reduction",88,"GetAcnodeReduction");
    int16_t rcfringe=0,byfringe=0;
    rc=((int(*)(void*,int16_t*,int16_t*))slot(p,92,"GetChromaticAberration"))(p,&rcfringe,&byfringe);
    out[@"chromatic_aberration"]=@{@"status":@(rc),@"rc_fringe":@(rcfringe),@"by_fringe":@(byfringe)};
    uint16_t shadingmode=0,shadingvalue=0;
    rc=((int(*)(void*,uint16_t*,uint16_t*))slot(p,95,"GetShadingValue"))(p,&shadingmode,&shadingvalue);
    out[@"shading"]=@{@"status":@(rc),@"mode":@(shadingmode),@"value":@(shadingvalue)};
    scalar(@"art_filter_mode",70,"GetArtFilterMode");
    uint16_t tone=0;int16_t bright=0,dark=0;
    rc=((int(*)(void*,uint16_t*,int16_t*,int16_t*))slot(p,102,"GetToneControlEPt"))(p,&tone,&bright,&dark);
    out[@"tone_control"]=@{@"status":@(rc),@"mode":@(tone),@"bright":@(bright),@"dark":@(dark)};
    bool enabled=((bool(*)(void*))slot(p,126,"IsMiddToneControlEnabled"))(p);
    out[@"midtone_supported"]=@(enabled);
    if(enabled){int16_t mid=0;rc=((int(*)(void*,uint16_t*,int16_t*,int16_t*,int16_t*))slot(p,127,"GetMiddToneControl"))(p,&tone,&bright,&mid,&dark);out[@"tone_control_with_mid"]=@{@"status":@(rc),@"mode":@(tone),@"bright":@(bright),@"dark":@(dark),@"mid":@(mid)};}
    auto channel=[&](NSString* key,int i,const char*name){
        uint16_t mode=0;void* array=nullptr;
        int status=((int(*)(void*,uint16_t*,void**))slot(p,i,name))(p,&mode,&array);
        NSMutableArray* values=[NSMutableArray array];
        if(!status&&array){
            unsigned count=((unsigned(*)(void*))slot(array,7,"GetSize"))(array);
            if(count>12){((unsigned(*)(void*))slot(array,4,"Release"))(array);throw std::runtime_error("unexpected profile vector length");}
            const int16_t* data=((const int16_t*(*)(void*))slot(array,8,"GetData"))(array);
            if(count&&!data){((unsigned(*)(void*))slot(array,4,"Release"))(array);throw std::runtime_error("missing profile vector data");}
            for(unsigned k=0;k<count;k++)[values addObject:@(data[k])];
        }
        if(array)((unsigned(*)(void*))slot(array,4,"Release"))(array);
        out[key]=@{@"status":@(status),@"mode":@(mode),@"values":values};
    };
    channel(@"saturation",110,"GetColorCreater2");
    channel(@"hue",135,"GetColorProfileHue");
    channel(@"luminance",139,"GetColorProfileLum");
    ((unsigned(*)(void*))slot(p,4,"Release"))(p);
    return out;
}
