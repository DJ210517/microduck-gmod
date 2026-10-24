#include "../physics_step/abi.h"
#include "bridge.h"
extern "C" __declspec(dllimport) int __stdcall GetModuleHandleExA(unsigned int,const char*,void**);
extern "C" __declspec(dllimport) unsigned int __stdcall GetModuleFileNameA(void*,char*,unsigned int);
using GarrysMod::Lua::ILuaBase;
using GarrysMod::Lua::CFunc;
static ILuaBase* Lua(lua_State* state) {ILuaBase* lua=state->luabase;lua->SetState(state);return lua;}
static int Handle(ILuaBase* lua) {
    double x=lua->CheckNumber(1);
    if(!(x>=1 && x<=800000000) || x!=static_cast<int>(x)) {lua->ArgError(1,"invalid integer simulation handle");return 0;}
    return static_cast<int>(x);
}
static bool Result(ILuaBase* lua,int success) {if(!success) lua->ThrowError(md_error());return success!=0;}
static void Array(ILuaBase* lua,const double* values,int count) {
    lua->CreateTable();for(int i=0;i<count;++i) {lua->PushNumber(i+1);lua->PushNumber(values[i]);lua->RawSet(-3);}
}
static void Field(ILuaBase* lua,const char* name,const double* values,int count) {Array(lua,values,count);lua->SetField(-2,name);}
static void Number(ILuaBase* lua,const char* name,double value) {lua->PushNumber(value);lua->SetField(-2,name);}
static void ReadArray(ILuaBase* lua,int argument,double* values,int count) {
    lua->CheckType(argument,5);
    for(int i=0;i<count;++i) {lua->PushNumber(i+1);lua->RawGet(argument);values[i]=lua->CheckNumber(-1);lua->Pop();}
}
static char module_path[4096],game_path[4096],data_path[4096],runtime_path[4096];
static bool ResolvePaths() {
    void* module=nullptr;
    if(!GetModuleHandleExA(6,reinterpret_cast<const char*>(&ResolvePaths),&module)) return false;
    unsigned int size=GetModuleFileNameA(module,module_path,4096);
    if(size==0 || size>=4096) return false;
    int n=int(size)-1;while(n>=0 && module_path[n]!='\\' && module_path[n]!='/') --n;
    if(n<8) return false;module_path[n]=0;
    const char* suffix="/lua/bin";
    for(int k=0;k<8;++k) {
        char c=module_path[n-8+k];if(c=='\\') c='/';if(c>='A' && c<='Z') c+=32;
        if(c!=suffix[k]) return false;
    }
    const int game_length=n-8;
    for(int k=0;k<game_length;++k) {game_path[k]=module_path[k];data_path[k]=module_path[k];}
    game_path[game_length]=0;
    const char* data_suffix="/data";for(int k=0;k<=5;++k) data_path[game_length+k]=data_suffix[k];
    if(n+12>=4096) return false;
    for(int k=0;k<n;++k) runtime_path[k]=module_path[k];
    const char* runtime_suffix="/mujoco.dll";for(int k=0;k<=11;++k) runtime_path[n+k]=runtime_suffix[k];
    return true;
}
static int Paths(lua_State* state) {
    ILuaBase* lua=Lua(state);
    if(!ResolvePaths()) {lua->ThrowError("microduck_mujoco must be loaded from garrysmod/lua/bin to resolve portable paths");return 0;}
    lua->CreateTable();
    lua->PushString(game_path);lua->SetField(-2,"game_dir");
    lua->PushString(data_path);lua->SetField(-2,"data_dir");
    lua->PushString(module_path);lua->SetField(-2,"lua_bin_dir");
    lua->PushString(runtime_path);lua->SetField(-2,"mujoco_dll");return 1;
}
static int Create(lua_State* state) {
    ILuaBase* lua=Lua(state);
    const char* xml=lua->CheckString(1);
    const char* path=nullptr;
    if(lua->IsType(2,4)) path=lua->CheckString(2);
    else {
        if(!ResolvePaths()) {lua->ThrowError("microduck_mujoco: cannot resolve adjacent portable MuJoCo DLL; supply its absolute path");return 0;}
        path=runtime_path;
    }
    if(!Result(lua,md_load(path))) return 0;
    int handle=md_create(xml);if(!Result(lua,handle)) return 0;
    lua->PushNumber(handle);return 1;
}
static int Destroy(lua_State* state) {ILuaBase* lua=Lua(state);if(!Result(lua,md_destroy(Handle(lua)))) return 0;lua->PushBool(true);return 1;}
static int Reset(lua_State* state) {
    ILuaBase* lua=Lua(state);double pos[3],quat[4];int h=Handle(lua);
    ReadArray(lua,2,pos,3);ReadArray(lua,3,quat,4);
    if(!Result(lua,md_reset(h,pos,quat))) return 0;lua->PushBool(true);return 1;
}
static int Snapshot(lua_State* state) {
    ILuaBase* lua=Lua(state);MDSnapshot value;
    if(!Result(lua,md_snapshot(Handle(lua),&value))) return 0;
    lua->CreateTable();Number(lua,"simtime",value.simtime);Number(lua,"pending_time",value.pending_time);
    Number(lua,"nq",value.nq);Number(lua,"nv",value.nv);
    Field(lua,"qpos",value.qpos,value.nq);Field(lua,"qvel",value.qvel,value.nv);
    lua->PushBool(value.motors_enabled!=0);lua->SetField(-2,"motors_enabled");return 1;
}
static int Restore(lua_State* state) {
    ILuaBase* lua=Lua(state);int h=Handle(lua);MDSnapshot value;lua->CheckType(2,5);
    lua->GetField(2,"nq");double nq=lua->CheckNumber(-1);lua->Pop();
    lua->GetField(2,"nv");double nv=lua->CheckNumber(-1);lua->Pop();
    if(!((nq==21 && nv==20) || (nq==25 && nv==24))) {lua->ThrowError("invalid MicroDuck snapshot dimensions");return 0;}
    value.nq=int(nq);value.nv=int(nv);
    lua->GetField(2,"qpos");ReadArray(lua,lua->Top(),value.qpos,value.nq);lua->Pop();
    lua->GetField(2,"qvel");ReadArray(lua,lua->Top(),value.qvel,value.nv);lua->Pop();
    lua->GetField(2,"simtime");value.simtime=lua->CheckNumber(-1);lua->Pop();
    lua->GetField(2,"pending_time");value.pending_time=lua->CheckNumber(-1);lua->Pop();
    lua->GetField(2,"motors_enabled");lua->CheckType(-1,1);value.motors_enabled=lua->GetBool(-1)?1:0;lua->Pop();
    if(!Result(lua,md_restore(h,&value))) return 0;lua->PushBool(true);return 1;
}
static int Step(lua_State* state) {
    ILuaBase* lua=Lua(state);int h=Handle(lua);double dt=lua->CheckNumber(2),targets[14];ReadArray(lua,3,targets,14);
    if(!Result(lua,md_step(h,dt,targets))) return 0;
    MDState output;if(!Result(lua,md_state(h,&output))) return 0;
    lua->PushNumber(output.advanced);return 1;
}
static int State(lua_State* state) {
    ILuaBase* lua=Lua(state);int h=Handle(lua);MDState value;
    if(!Result(lua,md_state(h,&value))) return 0;
    lua->CreateTable();Number(lua,"simtime",value.simtime);Number(lua,"pending_time",value.pending_time);Number(lua,"advanced",value.advanced);
    Field(lua,"q",value.q,14);Field(lua,"qd",value.qd,14);Field(lua,"gyro",value.gyro,3);Field(lua,"gravity",value.gravity,3);
    Field(lua,"root_position",value.root_position,3);Field(lua,"root_rotation",value.root_rotation,9);
    Field(lua,"root_velocity",value.root_velocity,3);
    double angles[4],velocities[4];if(!Result(lua,md_wheels(h,angles,velocities))) return 0;
    Field(lua,"wheel_angles",angles,4);Field(lua,"wheel_velocities",velocities,4);
    lua->CreateTable();
    for(int body=1;body<=value.body_count;++body) {
        double com[3],rotation[9];if(!Result(lua,md_body_pose(h,body,com,rotation))) return 0;
        lua->PushNumber(body);lua->CreateTable();Number(lua,"id",body);
        lua->PushString(md_body_name(h,body));lua->SetField(-2,"name");
        Field(lua,"com",com,3);Field(lua,"rotation",rotation,9);lua->RawSet(-3);
    }
    lua->SetField(-2,"bodies");return 1;
}
static int Proxy(lua_State* state) {
    ILuaBase* lua=Lua(state);int h=Handle(lua);double index=lua->CheckNumber(2),pos[3],quat[4],size[3];
    if(!(index>=1 && index<=32) || index!=static_cast<int>(index)) {lua->ArgError(2,"proxy index must be 1..32");return 0;}
    ReadArray(lua,3,pos,3);ReadArray(lua,4,quat,4);ReadArray(lua,5,size,3);
    const bool active=lua->Top()<6 || lua->GetBool(6);
    if(!Result(lua,md_proxy(h,int(index),pos,quat,size,active))) return 0;lua->PushBool(true);return 1;
}
static int Push(lua_State* state) {
    ILuaBase* lua=Lua(state);int h=Handle(lua);double body=lua->CheckNumber(2),force[3],torque[3];
    if(!(body>=1 && body<=MD_BODIES) || body!=static_cast<int>(body)) {lua->ArgError(2,"invalid robot body index");return 0;}
    ReadArray(lua,3,force,3);ReadArray(lua,4,torque,3);
    if(!Result(lua,md_push(h,int(body),force,torque))) return 0;lua->PushBool(true);return 1;
}
static int ProxyVelocity(lua_State* state) {
    ILuaBase* lua=Lua(state);int h=Handle(lua);double index=lua->CheckNumber(2),linear[3],angular[3];
    if(!(index>=1 && index<=32) || index!=static_cast<int>(index)) {lua->ArgError(2,"proxy index must be 1..32");return 0;}
    ReadArray(lua,3,linear,3);ReadArray(lua,4,angular,3);
    if(!Result(lua,md_proxy_velocity(h,int(index),linear,angular))) return 0;lua->PushBool(true);return 1;
}
static int Motors(lua_State* state) {
    ILuaBase* lua=Lua(state);int h=Handle(lua);lua->CheckType(2,1);
    if(!Result(lua,md_set_motors(h,lua->GetBool(2)))) return 0;lua->PushBool(true);return 1;
}
static int Contacts(lua_State* state) {
    ILuaBase* lua=Lua(state);int h=Handle(lua);MDState value;if(!Result(lua,md_state(h,&value))) return 0;
    lua->CreateTable();Number(lua,"dt",value.advanced);Number(lua,"overflow",md_contact_overflow(h));
    lua->CreateTable();int out=0;
    for(int p=1;p<=32;++p) {
        double linear[3],angular[3];if(!Result(lua,md_proxy_impulse(h,p,linear,angular))) return 0;
        bool nonzero=false;for(int k=0;k<3;++k) if(linear[k]!=0 || angular[k]!=0) nonzero=true;
        if(!nonzero) continue;
        lua->PushNumber(++out);lua->CreateTable();Number(lua,"index",p);Field(lua,"linear",linear,3);Field(lua,"angular",angular,3);lua->RawSet(-3);
    }
    lua->SetField(-2,"proxy_impulses");lua->CreateTable();int count=md_contact_count(h);
    for(int c=0;c<count;++c) {
        MDContact point;if(!Result(lua,md_contact(h,c,&point))) return 0;
        lua->PushNumber(c+1);lua->CreateTable();Number(lua,"body1",point.body1);Number(lua,"body2",point.body2);
        Number(lua,"geom1",point.geom1);Number(lua,"geom2",point.geom2);Number(lua,"proxy1",point.proxy1);Number(lua,"proxy2",point.proxy2);
        Field(lua,"pos",point.pos,3);Field(lua,"force_on_body2",point.force,3);Field(lua,"torque_on_body2",point.torque,3);
        Field(lua,"impulse_on_body2",point.impulse,3);Field(lua,"angular_impulse_on_body2",point.angular_impulse,3);lua->RawSet(-3);
    }
    lua->SetField(-2,"points");return 1;
}
static void Function(ILuaBase* lua,const char* name,CFunc fn) {lua->PushCFunction(fn);lua->SetField(-2,name);}
MD_EXPORT int gmod13_open(lua_State* state) {
    ILuaBase* lua=Lua(state);lua->CreateTable();
    Function(lua,"create",Create);Function(lua,"destroy",Destroy);Function(lua,"reset",Reset);Function(lua,"step",Step);Function(lua,"state",State);
    Function(lua,"snapshot",Snapshot);Function(lua,"restore",Restore);
    Function(lua,"set_proxy",Proxy);Function(lua,"push",Push);Function(lua,"applywrench",Push);Function(lua,"contacts",Contacts);
    Function(lua,"set_motors",Motors);
    Function(lua,"set_proxy_velocity",ProxyVelocity);
    Function(lua,"paths",Paths);
    lua->PushString("MuJoCo 3.17.0 / 5ms servo / passive roller wheels / guarded snapshots v4 / SI units");lua->SetField(-2,"version");
    lua->PushBool(true);lua->SetField(-2,"roller_support");
    Number(lua,"timestep",.005);Number(lua,"proxy_count",32);
    lua->Push(-1);lua->SetField(-10002,"microduck_mujoco");return 1;
}
MD_EXPORT int gmod13_close(lua_State*) {md_close_all();return 0;}
