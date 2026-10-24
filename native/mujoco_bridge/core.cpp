#include "bridge.h"
#include <mujoco/mjdata.h>
#include <mujoco/mjmodel.h>

// Use the installed headers for layout and dynamically bind only the C API.
// No STL, C++ runtime, constructors, allocation, exceptions, or Windows SDK.
extern "C" __declspec(dllimport) void* __stdcall LoadLibraryA(const char*);
extern "C" __declspec(dllimport) void* __stdcall GetProcAddress(void*,const char*);
extern "C" __declspec(dllimport) int __stdcall FreeLibrary(void*);
extern "C" __declspec(dllimport) double sqrt(double);
extern "C" { int _fltused=0; }

using LoadXML=mjModel* (*)(const char*,const void*,char*,int);
using MakeData=mjData* (*)(const mjModel*);
using ModelData=void (*)(const mjModel*,mjData*);
using NameId=int (*)(const mjModel*,int,const char*);
using IdName=const char* (*)(const mjModel*,int,int);
using ContactForce=void (*)(const mjModel*,const mjData*,int,mjtNum*);
static void* library;
static int (*version)();
static LoadXML load_xml;
static MakeData make_data;
static void (*delete_model)(mjModel*);
static void (*delete_data)(mjData*);
static ModelData step1,step2,forward,reset_data;
static void (*set_const)(mjModel*,mjData*);
static NameId name_id;
static IdName id_name;
static ContactForce contact_force;
static char last_error[1024];
static constexpr double H=.005,J=.0018,KP=.55,KD=.053,TORQUE=.96;
static const double HOME[14]={0,-.0873,-.4579,-.0049,.453,.3491,.3491,0,0,0,.0873,.4579,.0049,-.453};
static const char* JOINT_NAMES[14]={"left_hip_yaw","left_hip_roll","left_hip_pitch","left_knee","left_ankle","neck_pitch","head_pitch","head_yaw","head_roll","right_hip_yaw","right_hip_roll","right_hip_pitch","right_knee","right_ankle"};
static const char* WHEEL_NAMES[4]={"passive_LF_wheel","passive_LR_wheel","passive_RF_wheel","passive_RR_wheel"};
constexpr int MAX_CONTACTS=2048, MAX_INSTANCES=8;
struct Instance {
    mjModel* m;
    mjData* d;
    int generation, root,gyro, bodies[MD_BODIES],joint_q[14],joint_v[14],body_count,wheel_q[4],wheel_v[4];
    int proxy_body[32],proxy_geom[32],proxy_mocap[32];
    double pending,advanced;
    double proxy_impulses[32][6];
    double proxy_velocity[32][6];
    MDContact contacts[MAX_CONTACTS];
    int contact_count,overflow,faulted;
};
static Instance instances[MAX_INSTANCES];

static int fail(const char* message) {
    int i=0;
    for(;message && message[i] && i<1023;++i) last_error[i]=message[i];
    last_error[i]=0;
    return 0;
}
static bool finite(double x) { return x==x && x>-1e100 && x<1e100; }
static bool vector_ok(const double* x,int n,double limit=1e6) {
    if(!x) return false;
    for(int i=0;i<n;++i) if(!finite(x[i]) || x[i]<-limit || x[i]>limit) return false;
    return true;
}
static void copy(double* dst,const double* src,int n) { for(int i=0;i<n;++i) dst[i]=src[i]; }
static void zero(double* dst,int n) { for(int i=0;i<n;++i) dst[i]=0; }
static int physics_fault(Instance* s,const char* message) {
    s->faulted=1;s->contact_count=0;s->overflow=0;
    for(int p=0;p<32;++p) zero(s->proxy_impulses[p],6);
    zero(s->d->xfrc_applied,int(s->m->nbody)*6);
    return fail(message);
}
static bool solver_reset(const mjData* d) {
    // MuJoCo resets bad dynamics to qpos0 before returning, leaving a finite
    // state. These warning counts survive that automatic reset. A finite-only
    // check therefore misses the reset and would teleport a duck to the origin.
    return d->warning[mjWARN_BADQPOS].number || d->warning[mjWARN_BADQVEL].number ||
           d->warning[mjWARN_BADQACC].number || d->warning[mjWARN_BADCTRL].number;
}
static void number_name(char* dst,const char* prefix,int index) {
    int p=0;while(prefix[p]) {dst[p]=prefix[p];++p;}
    if(index>=10) dst[p++]=char('0'+index/10);
    dst[p++]=char('0'+index%10);dst[p]=0;
}
static Instance* get(int handle) {
    if(handle<=0) {fail("invalid simulation handle");return nullptr;}
    const int slot=(handle-1)%MAX_INSTANCES;
    Instance* s=&instances[slot];
    if(!s->m || s->generation!=(handle-1)/MAX_INSTANCES) {fail("stale or destroyed simulation handle");return nullptr;}
    return s;
}
static int proxy_index(const Instance* s,int body) {
    for(int p=0;p<32;++p) if(s->proxy_body[p]==body) return p+1;
    return 0;
}
static bool normalized_quat(const double* q,double* result) {
    if(!vector_ok(q,4,1e6)) return false;
    double norm=0;for(int i=0;i<4;++i) norm+=q[i]*q[i];
    if(norm<1e-16) return false;
    norm=sqrt(norm);for(int i=0;i<4;++i) result[i]=q[i]/norm;
    return true;
}
MD_EXPORT const char* md_error() {return last_error;}
MD_EXPORT int md_load(const char* path) {
    if(library) return 1;
    if(!path || !path[0]) return fail("MuJoCo DLL absolute path is required");
    library=LoadLibraryA(path);
    if(!library) return fail("could not load MuJoCo DLL or its dependencies");
#define BIND(variable,type,symbol) variable=reinterpret_cast<type>(GetProcAddress(library,symbol)); if(!variable) {FreeLibrary(library);library=nullptr;return fail("missing MuJoCo C API: " symbol);}
    BIND(version,int(*)(),"mj_version")
    if(version()!=3017000) {FreeLibrary(library);library=nullptr;return fail("MuJoCo version mismatch: this bridge requires 3.17.0 headers/runtime");}
    BIND(load_xml,LoadXML,"mj_loadXML")
    BIND(make_data,MakeData,"mj_makeData")
    BIND(delete_model,void(*)(mjModel*),"mj_deleteModel")
    BIND(delete_data,void(*)(mjData*),"mj_deleteData")
    BIND(step1,ModelData,"mj_step1")
    BIND(step2,ModelData,"mj_step2")
    BIND(forward,ModelData,"mj_forward")
    BIND(reset_data,ModelData,"mj_resetData")
    BIND(set_const,void(*)(mjModel*,mjData*),"mj_setConst")
    BIND(name_id,NameId,"mj_name2id")
    BIND(id_name,IdName,"mj_id2name")
    BIND(contact_force,ContactForce,"mj_contactForce")
#undef BIND
    last_error[0]=0;return 1;
}
MD_EXPORT int md_create(const char* xml_path) {
    if(!library) return fail("load MuJoCo before creating a simulation");
    int slot=0;while(slot<MAX_INSTANCES && instances[slot].m) ++slot;
    if(slot==MAX_INSTANCES) return fail("maximum eight live MicroDuck simulations reached");
    mjModel* m=load_xml(xml_path,nullptr,last_error,1024);
    if(!m) return 0;
    if(!((m->nq==21 && m->nv==20) || (m->nq==25 && m->nv==24)) || m->nbody<16 || m->nmocap>32) {delete_model(m);return fail("scene requires the free MicroDuck, 14 motors, optionally four passive wheels, and at most32 proxies");}
    Instance* s=&instances[slot];s->m=m;
    s->root=name_id(m,mjOBJ_BODY,"trunk_base");
    int gyro_id=name_id(m,mjOBJ_SENSOR,"imu_ang_vel");
    if(s->root<1 || gyro_id<0 || m->sensor_dim[gyro_id]!=3) {delete_model(m);s->m=nullptr;return fail("MicroDuck trunk or gyro sensor missing");}
    s->gyro=m->sensor_adr[gyro_id];
    s->bodies[0]=s->root;
    s->body_count=15;
    for(int i=0;i<14;++i) {
        int joint=name_id(m,mjOBJ_JOINT,JOINT_NAMES[i]);
        if(joint<0 || m->jnt_type[joint]!=mjJNT_HINGE) {delete_model(m);s->m=nullptr;return fail("required MicroDuck hinge missing");}
        s->joint_q[i]=m->jnt_qposadr[joint];s->joint_v[i]=m->jnt_dofadr[joint];
        s->bodies[i+1]=m->jnt_bodyid[joint];
    }
    m->opt.timestep=H;m->opt.integrator=mjINT_EULER;
    m->opt.disableflags|=mjDSBL_ACTUATION;
    for(int i=0;i<14;++i) {
        const int v=s->joint_v[i];
        m->dof_armature[v]=0;m->dof_damping[v]=0;m->dof_frictionloss[v]=TORQUE;
        m->dof_solref[2*v]=-5e4;m->dof_solref[2*v+1]=-200;
        double* imp=m->dof_solimp+5*v;imp[0]=.99;imp[1]=.9999;imp[2]=.001;imp[3]=.5;imp[4]=2;
    }
    for(int i=0;i<4;++i) {
        s->wheel_q[i]=s->wheel_v[i]=-1;
        if(m->nq==25) {
            int j=name_id(m,mjOBJ_JOINT,WHEEL_NAMES[i]);
            if(j<0 || m->jnt_type[j]!=mjJNT_HINGE) {delete_model(m);s->m=nullptr;return fail("roller scene missing a required passive wheel hinge");}
            s->wheel_q[i]=m->jnt_qposadr[j];s->wheel_v[i]=m->jnt_dofadr[j];
            s->bodies[15+i]=m->jnt_bodyid[j];
            // Official inference bearing resistance. Wheels retain their
            // original passive armature/damping and never receive motor torque.
            m->dof_frictionloss[s->wheel_v[i]]=.003;
            s->body_count=19;
        }
    }
    for(int a=0;a<m->nactuator;++a) m->actuator_armature[a]=0;
    for(int p=0;p<32;++p) {
        zero(s->proxy_velocity[p],6);
        char name[32];number_name(name,"md_proxy_",p+1);s->proxy_body[p]=name_id(m,mjOBJ_BODY,name);
        number_name(name,"md_proxy_geom_",p+1);s->proxy_geom[p]=name_id(m,mjOBJ_GEOM,name);
        s->proxy_mocap[p]=s->proxy_body[p]>=0 ? m->body_mocapid[s->proxy_body[p]] : -1;
        if(s->proxy_geom[p]>=0) {m->geom_contype[s->proxy_geom[p]]=0;m->geom_conaffinity[s->proxy_geom[p]]=0;}
        if(s->proxy_body[p]>=0) {m->body_contype[s->proxy_body[p]]=0;m->body_conaffinity[s->proxy_body[p]]=0;}
    }
    s->d=make_data(m);
    if(!s->d) {delete_model(m);s->m=nullptr;return fail("could not allocate MuJoCo simulation data");}
    set_const(m,s->d);
    const int handle=s->generation*MAX_INSTANCES+slot+1;
    double pos[3]={0,0,.125},quat[4]={1,0,0,0};
    md_reset(handle,pos,quat);
    return handle;
}
MD_EXPORT int md_destroy(int handle) {
    Instance* s=get(handle);if(!s) return 0;
    delete_data(s->d);delete_model(s->m);s->d=nullptr;s->m=nullptr;
    s->generation=(s->generation+1)%100000000;
    return 1;
}
MD_EXPORT int md_reset(int handle,const double* pos,const double* quat) {
    Instance* s=get(handle);if(!s) return 0;
    double normalized[4];if(!vector_ok(pos,3) || !normalized_quat(quat,normalized)) return fail("reset requires finite position and nonzero quaternion");
    // Reset only robot dynamics; externally supplied world proxy poses persist.
    double mocap_pos[96],mocap_quat[128];int mocaps=int(s->m->nmocap);
    copy(mocap_pos,s->d->mocap_pos,3*mocaps);copy(mocap_quat,s->d->mocap_quat,4*mocaps);
    reset_data(s->m,s->d);
    copy(s->d->mocap_pos,mocap_pos,3*mocaps);copy(s->d->mocap_quat,mocap_quat,4*mocaps);
    copy(s->d->qpos,pos,3);copy(s->d->qpos+3,normalized,4);
    for(int i=0;i<14;++i) s->d->qpos[s->joint_q[i]]=HOME[i];
    s->pending=0;s->advanced=0;s->contact_count=0;s->overflow=0;s->faulted=0;
    for(int p=0;p<32;++p) zero(s->proxy_impulses[p],6);
    forward(s->m,s->d);return 1;
}
MD_EXPORT int md_snapshot(int handle,MDSnapshot* result) {
    Instance* s=get(handle);if(!s || !result) return 0;
    if(s->faulted) return fail("physics simulation failed; reset before taking a snapshot");
    result->simtime=s->d->time;result->pending_time=s->pending;
    result->nq=int(s->m->nq);result->nv=int(s->m->nv);
    zero(result->qpos,MD_MAX_Q);zero(result->qvel,MD_MAX_V);
    copy(result->qpos,s->d->qpos,result->nq);copy(result->qvel,s->d->qvel,result->nv);
    result->motors_enabled=s->m->dof_frictionloss[s->joint_v[0]]>0?1:0;
    return 1;
}
MD_EXPORT int md_restore(int handle,const MDSnapshot* value) {
    Instance* s=get(handle);if(!s) return 0;
    if(!value || value->nq!=s->m->nq || value->nv!=s->m->nv || !finite(value->simtime) || value->simtime<0 || value->simtime>1e9 ||
       !finite(value->pending_time) || value->pending_time < -1e-12 || value->pending_time>=H ||
       !vector_ok(value->qpos,value->nq,1e8) || !vector_ok(value->qvel,value->nv,1e8) ||
       (value->motors_enabled!=0 && value->motors_enabled!=1))
        return fail("snapshot dimensions must match this robot, with finite state, nonnegative time and a motor flag");
    double norm=0;for(int i=3;i<7;++i) norm+=value->qpos[i]*value->qpos[i];
    if(norm<.999999 || norm>1.000001) return fail("snapshot root quaternion must have unit length");
    // Validate before mutating anything. Motor constants are recalculated on
    // scratch data, so a successful change does not perturb qpos or qvel.
    if((s->m->dof_frictionloss[s->joint_v[0]]>0)!=(value->motors_enabled!=0) &&
       !md_set_motors(handle,value->motors_enabled)) return 0;
    double mocap_pos[96],mocap_quat[128];int mocaps=int(s->m->nmocap);
    copy(mocap_pos,s->d->mocap_pos,3*mocaps);copy(mocap_quat,s->d->mocap_quat,4*mocaps);
    reset_data(s->m,s->d);
    copy(s->d->mocap_pos,mocap_pos,3*mocaps);copy(s->d->mocap_quat,mocap_quat,4*mocaps);
    copy(s->d->qpos,value->qpos,value->nq);copy(s->d->qvel,value->qvel,value->nv);s->d->time=value->simtime;
    s->pending=value->pending_time;s->advanced=0;s->contact_count=0;s->overflow=0;s->faulted=0;
    for(int p=0;p<32;++p) zero(s->proxy_impulses[p],6);
    // Rebuild transforms/contacts for the destination terrain. Old solver
    // warm starts and contact impulses must never cross scene boundaries.
    zero(s->d->qacc_warmstart,value->nv);forward(s->m,s->d);zero(s->d->qacc_warmstart,value->nv);
    return 1;
}
static void record_contacts(Instance* s) {
    mjModel* m=s->m;mjData* d=s->d;
    for(int c=0;c<d->ncon;++c) {
        const mjContact* contact=d->contact+c;
        if(contact->efc_address<0 || contact->geom[0]<0 || contact->geom[1]<0) continue;
        double local[6];contact_force(m,d,c,local);
        MDContact value;
        value.geom1=contact->geom[0];value.geom2=contact->geom[1];
        value.body1=m->geom_bodyid[value.geom1];value.body2=m->geom_bodyid[value.geom2];
        value.proxy1=proxy_index(s,value.body1);value.proxy2=proxy_index(s,value.body2);
        copy(value.pos,contact->pos,3);
        for(int axis=0;axis<3;++axis) {
            value.force[axis]=0;value.torque[axis]=0;
            for(int k=0;k<3;++k) {
                value.force[axis]+=contact->frame[3*k+axis]*local[k];
                value.torque[axis]+=contact->frame[3*k+axis]*local[k+3];
            }
            value.impulse[axis]=value.force[axis]*H;value.angular_impulse[axis]=value.torque[axis]*H;
        }
        for(int side=0;side<2;++side) {
            int p=(side?value.proxy2:value.proxy1)-1;if(p<0) continue;
            double sign=side?1:-1;double r[3],f[3];
            for(int axis=0;axis<3;++axis) {
                r[axis]=value.pos[axis]-d->xipos[3*s->proxy_body[p]+axis];f[axis]=sign*value.impulse[axis];
                s->proxy_impulses[p][axis]+=f[axis];s->proxy_impulses[p][axis+3]+=sign*value.angular_impulse[axis];
            }
            s->proxy_impulses[p][3]+=r[1]*f[2]-r[2]*f[1];
            s->proxy_impulses[p][4]+=r[2]*f[0]-r[0]*f[2];
            s->proxy_impulses[p][5]+=r[0]*f[1]-r[1]*f[0];
        }
        if(s->contact_count<MAX_CONTACTS) s->contacts[s->contact_count++]=value;
        else ++s->overflow;
    }
}
static void proxy_contact_velocity(Instance* s) {
    mjModel* m=s->m;mjData* d=s->d;
    for(int c=0;c<d->ncon;++c) {
        const mjContact* contact=d->contact+c;
        if(contact->efc_address<0 || contact->geom[0]<0 || contact->geom[1]<0) continue;
        double world[6]={0,0,0,0,0,0};bool moving=false;
        for(int side=0;side<2;++side) {
            int body=m->geom_bodyid[contact->geom[side]],p=proxy_index(s,body)-1;
            if(p<0) continue;
            const double* velocity=s->proxy_velocity[p];
            const double sign=side?1:-1;
            double r[3];for(int k=0;k<3;++k) r[k]=contact->pos[k]-d->xipos[3*body+k];
            double linear[3]={velocity[0]+velocity[4]*r[2]-velocity[5]*r[1],
                              velocity[1]+velocity[5]*r[0]-velocity[3]*r[2],
                              velocity[2]+velocity[3]*r[1]-velocity[4]*r[0]};
            for(int k=0;k<3;++k) {
                world[k]+=sign*linear[k];world[k+3]+=sign*velocity[k+3];
                moving=moving || linear[k]!=0 || velocity[k+3]!=0;
            }
        }
        if(!moving) continue;
        double local[6]={0,0,0,0,0,0};
        for(int k=0;k<3;++k) for(int axis=0;axis<3;++axis) {
            local[k]+=contact->frame[3*k+axis]*world[axis];
            local[k+3]+=contact->frame[3*k+axis]*world[axis+3];
        }
        const int first=contact->efc_address;
        // Equivalent to MuJoCo's mj_addSurfaceVel row mapping, extended to full
        // prescribed rigid-body velocity, including normal and angular motion.
        if(contact->dim==1 || m->opt.cone==mjCONE_ELLIPTIC) {
            for(int k=0;k<contact->dim;++k) {
                int row=first+k;d->efc_vel[row]+=local[k];d->efc_aref[row]-=d->efc_KBIP[4*row+1]*local[k];
            }
        } else {
            for(int k=1;k<contact->dim;++k) for(int side=0;side<2;++side) {
                int row=first+2*(k-1)+side;
                double delta=local[0]+(side?-1:1)*contact->friction[k-1]*local[k];
                d->efc_vel[row]+=delta;d->efc_aref[row]-=d->efc_KBIP[4*row+1]*delta;
            }
        }
    }
}
MD_EXPORT int md_step(int handle,double dt,const double* targets) {
    Instance* s=get(handle);if(!s) return 0;
    if(s->faulted) return fail("physics simulation failed; reset or restore a valid snapshot before stepping");
    if(!finite(dt) || dt<0 || dt>.1 || !vector_ok(targets,14,20)) return fail("step requires dt in [0,.1] and 14 finite radian targets");
    s->pending+=dt;s->advanced=0;s->contact_count=0;s->overflow=0;
    for(int p=0;p<32;++p) zero(s->proxy_impulses[p],6);
    mjModel* m=s->m;mjData* d=s->d;
    while(s->pending+1e-12>=H) {
        const double before=d->time;
        double velocity[14];
        for(int i=0;i<14;++i) velocity[i]=(J*d->qvel[s->joint_v[i]]+H*KP*(targets[i]-d->qpos[s->joint_q[i]]))/(J+H*KD);
        step1(m,d);
        if(solver_reset(d) || d->time!=before)
            return physics_fault(s,"MuJoCo rejected unstable dynamics; simulation stopped before an automatic position reset could be displayed");
        for(int row=0;row<d->nefc;++row) if(d->efc_type[row]==mjCNSTR_FRICTION_DOF) {
            int v=d->efc_id[row];
            for(int i=0;i<14;++i) if(s->joint_v[i]==v) {d->efc_aref[row]=(velocity[i]-d->qvel[v])/H;break;}
        }
        proxy_contact_velocity(s);
        step2(m,d);
        const double time_error=d->time-before-H;
        if(solver_reset(d) || !finite(d->time) || time_error < -1e-6 || time_error > 1e-6)
            return physics_fault(s,"MuJoCo rejected unstable dynamics; simulation stopped before an automatic position reset could be displayed");
        if(!vector_ok(d->qpos,int(m->nq),1e8) || !vector_ok(d->qvel,int(m->nv),1e8))
            return physics_fault(s,"nonfinite or unbounded physics state; simulation stopped");
        record_contacts(s);s->pending-=H;s->advanced+=H;
    }
    if(s->advanced>0) {
        zero(d->xfrc_applied,int(m->nbody)*6);
        // Refresh transforms/sensors to current state; contacts above are saved
        // before forward() replaces the solved motor/contact constraint forces.
        forward(m,d);
    }
    return 1;
}
MD_EXPORT int md_state(int handle,MDState* result) {
    Instance* s=get(handle);if(!s || !result) return 0;
    if(s->faulted) return fail("physics simulation failed; reset or restore a valid snapshot before reading dynamics");
    result->simtime=s->d->time;result->pending_time=s->pending;result->advanced=s->advanced;result->body_count=s->body_count;
    for(int i=0;i<14;++i) {result->q[i]=s->d->qpos[s->joint_q[i]];result->qd[i]=s->d->qvel[s->joint_v[i]];}
    copy(result->gyro,s->d->sensordata+s->gyro,3);
    const double* rot=s->d->xmat+s->root*9;
    for(int i=0;i<3;++i) result->gravity[i]=-rot[6+i];
    copy(result->root_position,s->d->xpos+s->root*3,3);copy(result->root_rotation,rot,9);
    copy(result->root_velocity,s->d->qvel,3);
    return 1;
}
MD_EXPORT int md_wheels(int handle,double* angles,double* velocities) {
    Instance* s=get(handle);if(!s || !angles || !velocities) return 0;
    for(int i=0;i<4;++i) {
        angles[i]=s->wheel_q[i]>=0?s->d->qpos[s->wheel_q[i]]:0;
        velocities[i]=s->wheel_v[i]>=0?s->d->qvel[s->wheel_v[i]]:0;
    }
    return 1;
}
MD_EXPORT const char* md_body_name(int handle,int body) {
    Instance* s=get(handle);if(!s || body<1 || body>s->body_count) return nullptr;
    return id_name(s->m,mjOBJ_BODY,s->bodies[body-1]);
}
MD_EXPORT int md_body_pose(int handle,int body,double* com,double* rotation) {
    Instance* s=get(handle);if(!s || body<1 || body>s->body_count || !com || !rotation) return fail("invalid robot body index");
    const int id=s->bodies[body-1];copy(com,s->d->xipos+3*id,3);copy(rotation,s->d->xmat+9*id,9);return 1;
}
MD_EXPORT int md_proxy(int handle,int index,const double* pos,const double* quat,const double* halfsize,int active) {
    Instance* s=get(handle);if(!s) return 0;
    if(index<1 || index>32) return fail("proxy index must be 1..32");
    int p=index-1,b=s->proxy_body[p],g=s->proxy_geom[p],mc=s->proxy_mocap[p];
    if(b<0 || g<0 || mc<0 || s->m->geom_type[g]!=mjGEOM_BOX) return fail("scene is missing the named mocap box proxy");
    const int bvh=s->m->body_bvhadr[b];
    if(s->m->body_geomnum[b]!=1 || s->m->body_bvhnum[b]!=1 || bvh<0 || bvh>=s->m->nbvhstatic || s->m->bvh_nodeid[bvh]!=g)
        return fail("proxy must have one compiled collision box and a single BVH leaf");
    for(int k=0;k<3;++k) if(s->m->body_ipos[3*b+k]!=0 || s->m->geom_pos[3*g+k]!=0)
        return fail("proxy box/inertial origins must coincide with body origin");
    for(int k=0;k<4;++k) if(s->m->body_iquat[4*b+k]!=(k==0?1:0) || s->m->geom_quat[4*g+k]!=(k==0?1:0))
        return fail("proxy box/inertial orientations must be identity; rotate using mocap quaternion");
    double normalized[4];
    if(!vector_ok(pos,3) || !normalized_quat(quat,normalized) || !vector_ok(halfsize,3,1000)) return fail("proxy requires finite position, quaternion and half extents");
    for(int axis=0;axis<3;++axis) if(halfsize[axis]<.0001) return fail("proxy half extents must be positive");
    copy(s->d->mocap_pos+3*mc,pos,3);copy(s->d->mocap_quat+4*mc,normalized,4);
    double radius=0;
    for(int axis=0;axis<3;++axis) {
        s->m->geom_size[3*g+axis]=halfsize[axis];s->m->geom_aabb[6*g+axis]=0;s->m->geom_aabb[6*g+axis+3]=halfsize[axis];radius+=halfsize[axis]*halfsize[axis];
    }
    s->m->geom_rbound[g]=sqrt(radius);
    // The midphase uses this body-inertial BVH leaf when the opposing body
    // contains multiple geoms (trunk/head). geom_aabb alone is insufficient.
    copy(s->m->bvh_aabb+6*bvh,s->m->geom_aabb+6*g,6);
    s->m->geom_contype[g]=active?1:0;s->m->geom_conaffinity[g]=active?1:0;
    s->m->body_contype[b]=active?1:0;s->m->body_conaffinity[b]=active?1:0;
    zero(s->proxy_velocity[p],6);
    return 1;
}
MD_EXPORT int md_proxy_velocity(int handle,int index,const double* linear,const double* angular) {
    Instance* s=get(handle);if(!s) return 0;
    if(index<1 || index>32 || s->proxy_mocap[index-1]<0 || !vector_ok(linear,3,10000) || !vector_ok(angular,3,10000))
        return fail("proxy velocity requires index 1..32 and finite world m/s, rad/s vectors");
    copy(s->proxy_velocity[index-1],linear,3);copy(s->proxy_velocity[index-1]+3,angular,3);return 1;
}
MD_EXPORT int md_push(int handle,int body,const double* force,const double* torque) {
    Instance* s=get(handle);if(!s) return 0;
    if(body<1 || body>s->body_count || !vector_ok(force,3) || !vector_ok(torque,3)) return fail("push requires a valid robot body index and finite world force/COM torque");
    int id=s->bodies[body-1];for(int axis=0;axis<3;++axis) {s->d->xfrc_applied[id*6+axis]+=force[axis];s->d->xfrc_applied[id*6+axis+3]+=torque[axis];}return 1;
}
MD_EXPORT int md_set_motors(int handle,int enabled) {
    Instance* s=get(handle);if(!s) return 0;
    // Recompute derived model constants using scratch data so toggling power
    // never resets or perturbs the actual generalized positions/velocities.
    mjData* scratch=make_data(s->m);
    if(!scratch) return fail("could not allocate scratch data to refresh motor constants");
    for(int i=0;i<14;++i) s->m->dof_frictionloss[s->joint_v[i]]=enabled?TORQUE:0;
    set_const(s->m,scratch);delete_data(scratch);forward(s->m,s->d);return 1;
}
MD_EXPORT int md_contact_count(int handle) {Instance* s=get(handle);return s?s->contact_count:-1;}
MD_EXPORT int md_contact(int handle,int index,MDContact* result) {
    Instance* s=get(handle);if(!s || !result || index<0 || index>=s->contact_count) return fail("invalid contact index");*result=s->contacts[index];return 1;
}
MD_EXPORT int md_proxy_impulse(int handle,int index,double* linear,double* angular) {
    Instance* s=get(handle);if(!s || index<1 || index>32 || !linear || !angular) return fail("invalid proxy index");copy(linear,s->proxy_impulses[index-1],3);copy(angular,s->proxy_impulses[index-1]+3,3);return 1;
}
MD_EXPORT int md_contact_overflow(int handle) {Instance* s=get(handle);return s?s->overflow:-1;}
MD_EXPORT void md_close_all() {
    for(int i=0;i<MAX_INSTANCES;++i) if(instances[i].m) md_destroy(instances[i].generation*MAX_INSTANCES+i+1);
    if(library) FreeLibrary(library);library=nullptr;
}
