-- Official roller command semantics: forward pushes, negative brakes,
-- command[3] is heading ERROR in radians. All four wheels stay passive.
local R={}
local function clamp(x,lo,hi)return math.max(lo,math.min(hi,x))end
local function wrap(x)return (x+math.pi)%(2*math.pi)-math.pi end
function R.reset(e,yaw)
    e.MicroDuckRollerState={target=yaw,phase='skate',elapsed=0,upright=false,stable=0,push=0}
end
function R.request(e,name)
    local s=e.MicroDuckRollerState
    if name=='toggle_sit' or name=='crouch' then
        if not s or not s.upright then return false,'Let the roller duck balance first.' end
        if s.phase~='skate' then return false,'Let the crouch finish first.' end
        s.phase='crouch';s.elapsed=0;s.push=0;return true
    end
    return false,'Kicks and somersaults use the walking duck. E performs a roller crouch.'
end
function R.update(e,dt,command,state)
    local r=state.root_rotation;local yaw=math.atan2(r[4],r[1])
    if not e.MicroDuckRollerState then R.reset(e,yaw) end
    local s=e.MicroDuckRollerState
    s.upright=state.gravity[3]<-.95
    local c={};for i=1,13 do c[i]=0 end
    local policy,phase='roller','skate'
    if s.phase=='crouch' then
        if s.elapsed<3.5-1e-9 then
            -- Upstream phase command: sin/cos over a five-second period,
            -- released3.5s window reaches phase0.7 before roller handback.
            local angle=2*math.pi*s.elapsed/5
            c[1],c[2]=math.cos(angle),math.sin(angle)
            policy,phase='roller_crouch','crouch';s.elapsed=s.elapsed+dt
        else s.phase='skate';s.target=yaw end
    end
    if policy=='roller' then
        command=command or {0,0,0}
        if state.gravity[3]>-.6 then s.phase='recover' end
        if s.phase=='recover' then
            phase='roller_recover';s.target=yaw;s.push=0
            local g=state.gyro;local v=state.root_velocity
            s.stable=(s.upright and g[1]^2+g[2]^2+g[3]^2<.64 and math.abs(v[3])<.2) and s.stable+dt or 0
            if s.stable>=.3 then s.phase='skate';phase='skate';s.stable=0 end
        else
            s.target=wrap(s.target+clamp(command[3] or 0,-1,1)*dt)
            local desired=clamp(command[1] or 0,-.3,.6)
            if desired<0 then
                local v=state.root_velocity
                local forward=r[1]*v[1]+r[4]*v[2]+r[7]*v[3]
                desired=-math.min(.3,math.max(0,forward)*1.5)
            end
            -- Ramp only the NN's command. Abrupt full push -> full brake can
            -- pitch the tiny skate model over, especially immediately turning.
            s.push=s.push+clamp(desired-s.push,-1.5*dt,1.5*dt)
            c[1]=s.push
            c[3]=clamp(wrap(s.target-yaw),-1,1)
        end
    end
    return {policy=policy,phase=phase,command=c,action_scale=.8}
end
return R
