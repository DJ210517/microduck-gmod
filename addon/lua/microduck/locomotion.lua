-- Idle correction changes only the learned policy's requested translation.
-- The robot still balances and brakes using its own joints and ground contacts.
local L={}
local function clamp(x,lo,hi) return math.max(lo,math.min(hi,x)) end
local function number(x)
    x=tonumber(x) or 0
    if x~=x or x==math.huge or x==-math.huge then return 0 end
    return x
end

function L.reset(e,position)
    position=position or {}
    e.MicroDuckLocomotionControl={x=number(position[1]),y=number(position[2]),vx=0,vy=0,slowVX=0,slowVY=0,moving=false,holding=false,settling=0}
end

function L.update(e,dt,requestedCommand,position,worldVelocity,yawRadians)
    position=position or {};worldVelocity=worldVelocity or {}
    requestedCommand=requestedCommand or {}
    if not e.MicroDuckLocomotionControl then L.reset(e,position) end
    local s=e.MicroDuckLocomotionControl
    local px,py=number(position[1]),number(position[2])
    local vx,vy,wz=number(requestedCommand[1]),number(requestedCommand[2]),number(requestedCommand[3])
    dt=clamp(number(dt),0,.1)
    -- Filter the small trunk oscillations of each footstep before braking.
    local alpha=dt/(.08+dt)
    s.vx=s.vx+(number(worldVelocity[1])-s.vx)*alpha
    s.vy=s.vy+(number(worldVelocity[2])-s.vy)*alpha
    local slowAlpha=dt/(.5+dt)
    s.slowVX=s.slowVX+(number(worldVelocity[1])-s.slowVX)*slowAlpha
    s.slowVY=s.slowVY+(number(worldVelocity[2])-s.slowVY)*slowAlpha
    local moving=math.abs(vx)+math.abs(vy)>.001
    if moving or s.moving then
        s.x,s.y=px,py
        s.holding=not moving
        s.settling=0
    end
    s.moving=moving
    if moving then return {vx,vy,wz} end

    local ex,ey=s.x-px,s.y-py
    local distance=math.sqrt(ex*ex+ey*ey)
    -- Begin accepting a stable landing within 6cm. Once qualification starts,
    -- allow body sway out to 8cm without resetting its timer.
    -- Reengage beyond 8cm so that boundary sway cannot toggle the hold.
    if not s.holding and distance>.08 then s.holding=true end
    local settlingRadius=s.settling>0 and .08 or .06
    if s.holding and distance<settlingRadius and s.slowVX*s.slowVX+s.slowVY*s.slowVY<.0009 then
        s.settling=s.settling+dt
        if s.settling>=.4 then
            s.holding=false
            s.x,s.y=px,py
            ex,ey,distance=0,0,0
        end
    else s.settling=0 end
    if not s.holding then ex,ey,distance=0,0,0 end
    if distance<.005 then ex,ey=0,0
    else
        local scale=(distance-.005)/distance
        ex,ey=ex*scale,ey*scale
    end
    local wx,wy=4*ex-.7*s.vx,4*ey-.7*s.vy
    local yaw=number(yawRadians)
    local c,sn=math.cos(yaw),math.sin(yaw)
    local x,y=c*wx+sn*wy,-sn*wx+c*wy
    local magnitude=math.sqrt(x*x+y*y)
    if magnitude>.15 then x,y=x*.15/magnitude,y*.15/magnitude end
    s.errorX,s.errorY,s.outputX,s.outputY=ex,ey,x,y
    return {x,y,wz}
end

return L
