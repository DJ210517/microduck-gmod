#pragma once

// Narrow ABI prefixes; source snapshots and URLs are in reference/ and ABI.md.
// Windows x64 MSVC ABI only. These interfaces are borrowed, never instantiated.
#if !defined(_WIN32) || (!defined(_M_X64) && !defined(__x86_64__))
#error This module supports Windows x64 only.
#endif
static_assert(sizeof(void*) == 8, "Expected Windows x64 pointers");
static_assert(sizeof(float) == 4 && sizeof(double) == 8, "Unexpected floating ABI");

class Vector;
class QAngle;
struct lua_State;
namespace GarrysMod { namespace Lua {
using CFunc = int (*)(lua_State*);
class ILuaBase {
public:
    virtual int Top() = 0;
    virtual void Push(int) = 0;
    virtual void Pop(int = 1) = 0;
    virtual void GetTable(int) = 0;
    virtual void GetField(int, const char*) = 0;
    virtual void SetField(int, const char*) = 0;
    virtual void CreateTable() = 0;
    virtual void SetTable(int) = 0;
    virtual void SetMetaTable(int) = 0;
    virtual bool GetMetaTable(int) = 0;
    virtual void Call(int, int) = 0;
    virtual int PCall(int, int, int) = 0;
    virtual int Equal(int, int) = 0;
    virtual int RawEqual(int, int) = 0;
    virtual void Insert(int) = 0;
    virtual void Remove(int) = 0;
    virtual int Next(int) = 0;
    virtual void* NewUserdata(unsigned int) = 0;
    virtual void ThrowError(const char*) = 0;
    virtual void CheckType(int, int) = 0;
    virtual void ArgError(int, const char*) = 0;
    virtual void RawGet(int) = 0;
    virtual void RawSet(int) = 0;
    virtual const char* GetString(int = -1, unsigned int* = nullptr) = 0;
    virtual double GetNumber(int = -1) = 0;
    virtual bool GetBool(int = -1) = 0;
    virtual CFunc GetCFunction(int = -1) = 0;
    virtual void* GetUserdata(int = -1) = 0;
    virtual void PushNil() = 0;
    virtual void PushString(const char*, unsigned int = 0) = 0;
    virtual void PushNumber(double) = 0;
    virtual void PushBool(bool) = 0;
    virtual void PushCFunction(CFunc) = 0;
    virtual void PushCClosure(CFunc, int) = 0;
    virtual void PushUserdata(void*) = 0;
    virtual int ReferenceCreate() = 0;
    virtual void ReferenceFree(int) = 0;
    virtual void ReferencePush(int) = 0;
    virtual void PushSpecial(int) = 0;
    virtual bool IsType(int, int) = 0;
    virtual int GetType(int) = 0;
    virtual const char* GetTypeName(int) = 0;
    virtual void CreateMetaTableType(const char*, int) = 0;
    virtual const char* CheckString(int = -1) = 0;
    virtual double CheckNumber(int = -1) = 0;
    virtual int ObjLen(int = -1) = 0;
    virtual const QAngle& GetAngle(int = -1) = 0;
    virtual const Vector& GetVector(int = -1) = 0;
    virtual void PushAngle(const QAngle&) = 0;
    virtual void PushVector(const Vector&) = 0;
    virtual void SetState(lua_State*) = 0; // slot 50
};
}}
struct lua_State {
    unsigned char common_header[92 + 22];
    GarrysMod::Lua::ILuaBase* luabase;
};
static_assert(__builtin_offsetof(lua_State, luabase) == 120, "Incorrect GMod x64 Lua ABI");

using CreateInterfaceFn = void* (*)(const char*, int*);
class IPhysicsEnvironment;
struct AppSystemInfo_t;
class IAppSystem {
public:
    virtual bool Connect(CreateInterfaceFn) = 0;
    virtual void Disconnect() = 0;
    virtual void* QueryInterface(const char*) = 0;
    virtual int Init() = 0;
    virtual void Shutdown() = 0;
    // GMod's installed x64 engine uses the newer nine-method IAppSystem.
    // Valve's SDK2013 header has only five and MUST NOT define this prefix.
    // Slots 5..8 are never called here; verified in the installed vphysics.dll.
    virtual const AppSystemInfo_t* GetDependencies() = 0;
    virtual int GetTier() = 0;
    virtual void Reconnect(CreateInterfaceFn, const char*) = 0;
    virtual bool IsSingleton() = 0;
};
class IPhysics : public IAppSystem {
public:
    virtual IPhysicsEnvironment* CreateEnvironment() = 0;
    virtual void DestroyEnvironment(IPhysicsEnvironment*) = 0;
    virtual IPhysicsEnvironment* GetActiveEnvironmentByIndex(int) = 0; // slot 11
};

class IVPhysicsDebugOverlay;
class IPhysicsObject;
class CPhysCollide;
class IPhysicsFluidController;
class IPhysicsSpring;
class IPhysicsConstraint;
class IPhysicsConstraintGroup;
class IPhysicsShadowController;
class IPhysicsPlayerController;
class IPhysicsMotionController;
class IPhysicsVehicleController;
class IPhysicsGameTrace;
class IPhysicsCollisionSolver;
class IMotionEvent;
struct objectparams_t;
struct fluidparams_t;
struct springparams_t;
struct constraint_ragdollparams_t;
struct constraint_hingeparams_t;
struct constraint_fixedparams_t;
struct constraint_slidingparams_t;
struct constraint_ballsocketparams_t;
struct constraint_pulleyparams_t;
struct constraint_lengthparams_t;
struct constraint_groupparams_t;
struct vehicleparams_t;

class IPhysicsEnvironment {
public:
    virtual ~IPhysicsEnvironment() {} // MSVC x64 scalar deleting destructor: slot 0
    virtual void SetDebugOverlay(CreateInterfaceFn) = 0;
    virtual IVPhysicsDebugOverlay* GetDebugOverlay() = 0;
    virtual void SetGravity(const Vector&) = 0;
    virtual void GetGravity(Vector*) const = 0;
    virtual void SetAirDensity(float) = 0;
    virtual float GetAirDensity() const = 0;
    virtual IPhysicsObject* CreatePolyObject(const CPhysCollide*, int, const Vector&, const QAngle&, objectparams_t*) = 0;
    virtual IPhysicsObject* CreatePolyObjectStatic(const CPhysCollide*, int, const Vector&, const QAngle&, objectparams_t*) = 0;
    virtual IPhysicsObject* CreateSphereObject(float, int, const Vector&, const QAngle&, objectparams_t*, bool) = 0;
    virtual void DestroyObject(IPhysicsObject*) = 0;
    virtual IPhysicsFluidController* CreateFluidController(IPhysicsObject*, fluidparams_t*) = 0;
    virtual void DestroyFluidController(IPhysicsFluidController*) = 0;
    virtual IPhysicsSpring* CreateSpring(IPhysicsObject*, IPhysicsObject*, springparams_t*) = 0;
    virtual void DestroySpring(IPhysicsSpring*) = 0;
    virtual IPhysicsConstraint* CreateRagdollConstraint(IPhysicsObject*, IPhysicsObject*, IPhysicsConstraintGroup*, const constraint_ragdollparams_t&) = 0;
    virtual IPhysicsConstraint* CreateHingeConstraint(IPhysicsObject*, IPhysicsObject*, IPhysicsConstraintGroup*, const constraint_hingeparams_t&) = 0;
    virtual IPhysicsConstraint* CreateFixedConstraint(IPhysicsObject*, IPhysicsObject*, IPhysicsConstraintGroup*, const constraint_fixedparams_t&) = 0;
    virtual IPhysicsConstraint* CreateSlidingConstraint(IPhysicsObject*, IPhysicsObject*, IPhysicsConstraintGroup*, const constraint_slidingparams_t&) = 0;
    virtual IPhysicsConstraint* CreateBallsocketConstraint(IPhysicsObject*, IPhysicsObject*, IPhysicsConstraintGroup*, const constraint_ballsocketparams_t&) = 0;
    virtual IPhysicsConstraint* CreatePulleyConstraint(IPhysicsObject*, IPhysicsObject*, IPhysicsConstraintGroup*, const constraint_pulleyparams_t&) = 0;
    virtual IPhysicsConstraint* CreateLengthConstraint(IPhysicsObject*, IPhysicsObject*, IPhysicsConstraintGroup*, const constraint_lengthparams_t&) = 0;
    virtual void DestroyConstraint(IPhysicsConstraint*) = 0;
    virtual IPhysicsConstraintGroup* CreateConstraintGroup(const constraint_groupparams_t&) = 0;
    virtual void DestroyConstraintGroup(IPhysicsConstraintGroup*) = 0;
    virtual IPhysicsShadowController* CreateShadowController(IPhysicsObject*, bool, bool) = 0;
    virtual void DestroyShadowController(IPhysicsShadowController*) = 0;
    virtual IPhysicsPlayerController* CreatePlayerController(IPhysicsObject*) = 0;
    virtual void DestroyPlayerController(IPhysicsPlayerController*) = 0;
    virtual IPhysicsMotionController* CreateMotionController(IMotionEvent*) = 0;
    virtual void DestroyMotionController(IPhysicsMotionController*) = 0;
    virtual IPhysicsVehicleController* CreateVehicleController(IPhysicsObject*, const vehicleparams_t&, unsigned int, IPhysicsGameTrace*) = 0;
    virtual void DestroyVehicleController(IPhysicsVehicleController*) = 0;
    virtual void SetCollisionSolver(IPhysicsCollisionSolver*) = 0;
    virtual void Simulate(float) = 0;
    virtual bool IsInSimulation() const = 0; // slot 35
    virtual float GetSimulationTimestep() const = 0; // slot 36
    virtual void SetSimulationTimestep(float) = 0; // slot 37
};
