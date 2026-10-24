-- Official learned policy scheduling; no poses, animation or support forces.
-- Sources and measured roll-window adjustment: data_static/microduck_skills/provenance.json.
local S={sit_seconds=2,rise_seconds=1,roll_min_seconds=1,roll_max_seconds=5,kick_seconds=.5}
local atan2=math.atan2 or math.atan
local function finite(x)
    return type(x)=="number" and x==x and x~=math.huge and x~=-math.huge
end
local function zeroCommand()
    local c={};for i=1,13 do c[i]=0 end;return c
end
local function enter(s,phase,remaining)
    s.phase,s.remaining,s.stable=phase,remaining or 0,0
    if phase=="roll" then s.rollAngle,s.rollProgress,s.rollElapsed=nil,0,0 end
end
function S.reset(e)
    e.MicroDuckSkillState={phase="walk",remaining=0,stable=0,upright=false,still=false}
end
function S.status(e)
    local s=e.MicroDuckSkillState
    return s and s.phase or "walk"
end
function S.request(e,request)
    if not e.MicroDuckSkillState then S.reset(e) end
    local s=e.MicroDuckSkillState
    if request=="toggle" or request=="toggle_sit" then request=(s.phase=="sit" or s.phase=="hold") and "stand" or "sit" end
    if request=="sit" then
        if s.phase=="sit" or s.phase=="hold" then return true end
        if s.phase~="walk" then return false,"Wait for the current movement to finish." end
        if not s.upright then return false,"Let the duck stand upright first." end
        enter(s,"sit",S.sit_seconds)
    elseif request=="stand" or request=="walk" then
        if s.phase=="walk" or s.phase=="rise" or s.phase=="recover" then return true end
        if s.phase=="sit" then return false,"The duck is still sitting down." end
        if s.phase~="hold" then return false,"Let the current movement finish first." end
        enter(s,"rise",S.rise_seconds)
    elseif request=="roll" or request=="roulade" then
        if s.phase~="walk" then return false,"Stand up before rolling." end
        if not s.upright or not s.still then return false,"Let the duck stop and balance before rolling." end
        enter(s,"roll")
    elseif request=="kick_left" or request=="kick_right" then
        if s.phase~="walk" then return false,"Stand up and finish the current movement before kicking." end
        if not s.upright or not s.still then return false,"Let the duck stop and balance before kicking." end
        enter(s,request,S.kick_seconds)
    else return false,"Unknown MicroDuck skill." end
    return true
end
function S.update(e,dt,walkCommand,state)
    if not e.MicroDuckSkillState then S.reset(e) end
    local s=e.MicroDuckSkillState
    dt=finite(dt) and math.max(0,math.min(dt,.1)) or 0
    state=state or {};local g=state.gravity or {};local gyro=state.gyro or {};local v=state.root_velocity or {}
    local angular=0
    for i=1,3 do local x=gyro[i];angular=angular+(finite(x) and x*x or math.huge) end
    s.upright=finite(g[3]) and g[3]<-.95
    s.still=finite(v[1]) and finite(v[2]) and v[1]*v[1]+v[2]*v[2]<.0025 and angular<.64
    local returned=false
    if s.phase=="walk" then
        s.falling=(finite(g[3]) and g[3]>-.6) and (s.falling or 0)+dt or 0
        if s.falling>=.1 then enter(s,"recover");s.falling=0 end
    else s.falling=0 end
    if s.phase=="roll" then
        -- The policy owns every joint action. Measure its physical progress so
        -- walking does not interrupt an unfinished roll or allow a second one.
        if finite(g[1]) and finite(g[3]) then
            local angle=atan2(g[1],-g[3])
            local delta=(angle-(s.rollAngle or angle)+math.pi)%(2*math.pi)-math.pi
            s.rollAngle=angle;s.rollProgress=s.rollProgress+delta
        end
        -- Five seconds is the training episode length; a blocked roll then
        -- yields to the learned recovery policy rather than repeating forever.
        local complete=s.rollElapsed>=S.roll_min_seconds and s.rollProgress>=5.75 and s.upright
        if complete or s.rollElapsed>=S.roll_max_seconds-1e-9 then
            s.rollCompleted=complete
            enter(s,"recover")
        end
    end
    -- Match upstream: expire before inference, advance clocks after selecting
    -- this tick's network. The full final policy tick is therefore preserved.
    if s.remaining<=1e-9 then
        if s.phase=="sit" then enter(s,"hold")
        elseif s.phase=="rise" or s.phase=="kick_left" or s.phase=="kick_right" then enter(s,"recover") end
    end
    if s.phase=="recover" then
        -- Velstand itself gets the duck upright. Keep its trained zero command
        -- while recovering, then let heading/position controllers recapture.
        local landing=finite(v[3]) and math.abs(v[3])<.2
        s.stable=(s.upright and angular<.64 and landing) and s.stable+dt or 0
        if s.stable>=.3 then enter(s,"walk");returned=true end
    end
    local command=zeroCommand();local policy="walk"
    if s.phase=="sit" or s.phase=="hold" then policy="sitstand";command[1]=1
    elseif s.phase=="rise" then policy="sitstand"
    elseif s.phase=="roll" then policy="roulade"
    elseif s.phase=="kick_left" or s.phase=="kick_right" then policy=s.phase
    elseif s.phase=="walk" and not returned then
        walkCommand=walkCommand or {}
        for i=1,3 do command[i]=finite(walkCommand[i]) and walkCommand[i] or 0 end
    end
    local descriptor={policy=policy,phase=s.phase,command=command,action_scale=1,returned_to_walk=returned}
    s.remaining=math.max(0,s.remaining-dt)
    if s.phase=="roll" then s.rollElapsed=s.rollElapsed+dt end
    return descriptor
end
return S
