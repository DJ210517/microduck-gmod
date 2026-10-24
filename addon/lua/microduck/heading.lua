-- Heading feedback changes the neural policy's requested yaw rate only.
-- It never applies a force, torque, pose, or velocity to the robot.
local H={}
local pi,tau=math.pi,2*math.pi
local function clamp(x,lo,hi) return math.max(lo,math.min(hi,x)) end
local function wrap(x) return (x+pi)%tau-pi end
local function number(x)
    x=tonumber(x) or 0
    if x~=x or x==math.huge or x==-math.huge then return 0 end
    return x
end

function H.reset(e,worldHeadingRadians)
    e.MicroDuckHeadingControl={target=wrap(number(worldHeadingRadians)),integral=0,error=0,output=0}
end

function H.update(e,dt,requestedCommand,yawRadians,yawRateRadians)
    local yaw=wrap(number(yawRadians))
    if not e.MicroDuckHeadingControl then H.reset(e,yaw) end
    local s=e.MicroDuckHeadingControl
    local command=requestedCommand or {}
    local turn=clamp(number(command[3]),-1,1)
    dt=clamp(number(dt),0,.1)
    -- Follow the user's turning request, then hold that heading on release.
    s.target=wrap(s.target+turn*dt)
    local err=wrap(s.target-yaw)
    local base=turn+2*err+.2*(turn-number(yawRateRadians))
    local integral=clamp(s.integral+err*dt,-1,1)
    local candidate=base+.3*integral
    -- Integrate only if it can help, or if it unwinds existing saturation.
    if not ((candidate>1 and err>0) or (candidate< -1 and err<0)) then
        s.integral=integral
    end
    s.error=err
    s.output=clamp(base+.3*s.integral,-1,1)
    return {number(command[1]),number(command[2]),s.output}
end

return H
