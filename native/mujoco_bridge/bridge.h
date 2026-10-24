#pragma once
#define MD_EXPORT extern "C" __declspec(dllexport)
constexpr int MD_JOINTS=14, MD_BODIES=19, MD_PROXIES=32, MD_MAX_Q=25, MD_MAX_V=24;
struct MDState {
    double simtime, pending_time, advanced;
    double q[14], qd[14], gyro[3], gravity[3];
    double root_position[3], root_rotation[9];
    double root_velocity[3];
    int body_count;
};
struct MDContact {
    int body1,body2,geom1,geom2,proxy1,proxy2;
    double pos[3],force[3],torque[3],impulse[3],angular_impulse[3];
};
// Robot dynamics only. Terrain/proxies belong to the destination scene and
// controller history/queued external impulses belong to the Lua entity.
struct MDSnapshot {
    double simtime,pending_time;
    double qpos[MD_MAX_Q],qvel[MD_MAX_V];
    int motors_enabled,nq,nv;
};
MD_EXPORT const char* md_error();
MD_EXPORT int md_load(const char* dll_path);
MD_EXPORT int md_create(const char* xml_path);
MD_EXPORT int md_destroy(int handle);
MD_EXPORT int md_reset(int handle,const double* pos,const double* quat);
MD_EXPORT int md_snapshot(int handle,MDSnapshot* result);
MD_EXPORT int md_restore(int handle,const MDSnapshot* snapshot);
MD_EXPORT int md_step(int handle,double dt,const double* targets);
MD_EXPORT int md_state(int handle,MDState* result);
MD_EXPORT int md_wheels(int handle,double* angles,double* velocities);
MD_EXPORT const char* md_body_name(int handle,int body);
MD_EXPORT int md_body_pose(int handle,int body,double* com,double* rotation);
MD_EXPORT int md_proxy(int handle,int index,const double* pos,const double* quat,const double* halfsize,int active);
MD_EXPORT int md_proxy_velocity(int handle,int index,const double* linear,const double* angular);
MD_EXPORT int md_push(int handle,int body,const double* force,const double* torque);
MD_EXPORT int md_set_motors(int handle,int enabled);
MD_EXPORT int md_contact_count(int handle);
MD_EXPORT int md_contact(int handle,int index,MDContact* result);
MD_EXPORT int md_proxy_impulse(int handle,int index,double* linear,double* angular);
MD_EXPORT int md_contact_overflow(int handle);
MD_EXPORT void md_close_all();
