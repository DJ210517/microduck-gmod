AddCSLuaFile("shared.lua")
AddCSLuaFile("cl_init.lua")
AddCSLuaFile("microduck/link.lua")
AddCSLuaFile("microduck/control.lua")
include("shared.lua")

local Network = include("microduck/network.lua")
local Runtime = include("microduck/mujoco_runtime.lua")
local World = include("microduck/mujoco_world.lua")
local Render = include("microduck/mujoco_render_data.lua")
local Heading = include("microduck/heading.lua")
local Locomotion = include("microduck/locomotion.lua")
local Skills = include("microduck/skills.lua")
local Roller = include("microduck/roller.lua")
local H, POLICY_STEPS, U = .005, 4, Render.units_per_m
local MAX_DETAIL_CONTACTS = 256
MicroDuck = MicroDuck or {}
local MD = MicroDuck
MD.Active = MD.Active or {}

local function vec(a) return Vector(a[1], a[2], a[3]) end
local function arr(v) return {v.x, v.y, v.z} end
local function finite(x) return type(x) == "number" and x == x and math.abs(x) < 1e8 end
local function finiteVector(v) return v and finite(v.x) and finite(v.y) and finite(v.z) end
local function quaternion(a)
    local p, y, r = math.rad(a.p) * .5, math.rad(a.y) * .5, math.rad(a.r) * .5
    local cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
    return {cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy}
end
local function modelAngle(a, b)
    local c = {}
    for r = 1, 3 do for col = 1, 3 do
        c[(r - 1) * 3 + col] = a[(r - 1) * 3 + 1] * b[1][col] +
            a[(r - 1) * 3 + 2] * b[2][col] + a[(r - 1) * 3 + 3] * b[3][col]
    end end
    return Angle(math.deg(math.atan2(-c[7], math.sqrt(c[1]^2 + c[4]^2))),
        math.deg(math.atan2(c[4], c[1])), math.deg(math.atan2(c[8], c[9])))
end
local function nativeRuntime(roller)
    -- Load on spawn: a missing dependency remains a visible entity error rather
    -- than preventing the addon or its controls from loading.
    require(MD.NativeModule or "microduck_mujoco")
    local native = assert(microduck_mujoco, "MicroDuck native module did not load")
    assert(native.paths and native.set_proxy_velocity, "MicroDuck native module is outdated; reinstall and restart GMod")
    assert(native.snapshot and native.restore, "MicroDuck physics runtime needs updating; install the new runtime and restart GMod")
    assert(not roller or native.roller_support, "Roller duck needs the v4 native runtime; install it and restart GMod")
    local ready, err = Runtime.prepare(native.paths(),roller and "roller" or nil)
    assert(ready, err)
    MD.Weights = MD.Weights or assert(util.JSONToTable(include("microduck/policy_data.lua"), true), "Missing MicroDuck neural policy")
    MD.SkillWeights = MD.SkillWeights or {}
    for _, name in ipairs({"sitstand", "roulade", "kick_left", "kick_right"}) do
        MD.SkillWeights[name] = MD.SkillWeights[name] or assert(util.JSONToTable(include("microduck/policy_" .. name .. "_data.lua"), true), "Missing MicroDuck policy: " .. name)
    end
    if roller and not MD.RollerWeights then
        MD.RollerWeights={}
        for _,name in ipairs({"roller","roller_crouch"}) do MD.RollerWeights[name]=assert(util.JSONToTable(include("microduck/policy_"..name.."_data.lua"),true),"Missing roller policy") end
    end
    return native, ready
end

function ENT:SpawnFunction(ply, tr)
    if not tr.Hit then return end
    local e = ents.Create(self.MicroDuckRoller and "md_microduck_roller" or "md_microduck")
    e.Creator, e.SpawnFloor = ply, tr.HitPos
    e:SetPos(tr.HitPos + Vector(0, 0, .125 * U))
    e:SetAngles(Angle(0, IsValid(ply) and ply:EyeAngles().y or 0, 0))
    e:Spawn(); e:Activate()
    if IsValid(ply) then ply.MicroDuck = e end
    return e
end

function ENT:SetSimulationError(message)
    self.PolicyError = tostring(message)
    MD.Active[self] = nil
    self:SetMotorsEnabled(false)
    local first = string.match(self.PolicyError, "^[^\r\n]+") or "Unknown simulation error"
    self:SetNWString("MicroDuckError", string.sub(first, 1, 220))
    file.CreateDir("microduck_mj")
    file.Write("microduck_mj/error_" .. self:EntIndex() .. ".txt", self.PolicyError)
    ErrorNoHalt("[MicroDuck] Simulation stopped; microduck_reset retries. " .. self.PolicyError .. "\n")
end

function ENT:Initialize()
    self.Render=self.MicroDuckRoller and include("microduck/mujoco_roller_render_data.lua") or Render
    self.Links, self.Proxies, self.ProxyCenters, self.PendingImpulses = {self}, {}, {}, {}
    self.SpawnYaw = self:GetAngles().y
    if self.SpawnFloor then
        self.WorldOrigin = Vector(self.SpawnFloor.x, self.SpawnFloor.y, self.SpawnFloor.z)
    else
        local tr = util.TraceLine({start = self:GetPos() + Vector(0, 0, 50),
            endpos = self:GetPos() - Vector(0, 0, 100), mask = MASK_SOLID_BRUSHONLY, filter = self})
        self.WorldOrigin = tr.Hit and tr.HitPos or self:GetPos() - Vector(0, 0, .125 * U)
    end
    self:SetModel(self.Render.links[1].model)
    self:SetUseType(SIMPLE_USE)
    self:SetNWEntity("MicroDuckRoot", self)
    self.MicroDuckRoot, self.MicroDuckMJRoot, self.MicroDuckBodyIndex = self, self, 1
    self:SetNWFloat("MicroDuckHeading", self.SpawnYaw)
    self:SetNWFloat("MicroDuckRate", 1)
    self:SetNWString("MicroDuckPhysics", "MuJoCo")
    self:SetNWBool("MicroDuckRoller",self.MicroDuckRoller==true)
    self:SetNWString("MicroDuckError", "")
    local ok, err = xpcall(function() self:InitializeNative() end, debug.traceback)
    if not ok then self:SetSimulationError(err) end
end

function ENT:InitializeNative()
    self.NativeInitialized = false
    self:ReleaseNative()
    self.Native, self.Runtime = nativeRuntime(self.MicroDuckRoller)
    local xml, metadata = World.buildXML(self.WorldOrigin, self.Runtime.base_xml, 1024)
    assert(xml, metadata)
    self.WorldMetadata = metadata
    local scene, err = Runtime.writeScene(self.Runtime, "world_" .. self:EntIndex(), xml)
    assert(scene, err)
    self.SceneDataPath = self.Runtime.data_path .. "/world_" .. self:EntIndex() .. ".xml"
    self.NativeHandle = self.Native.create(scene, self.Runtime.mujoco_dll)
    self.Networks = {}
    if self.MicroDuckRoller then
        for name,weights in pairs(MD.RollerWeights) do self.Networks[name]=Network.new(weights) end
        self.Network=self.Networks.roller
    else
        self.Network = Network.new(MD.Weights);self.Networks.walk=self.Network
        for name, weights in pairs(MD.SkillWeights) do self.Networks[name] = Network.new(weights) end
    end
    self.Native.reset(self.NativeHandle, {0, 0, self.MicroDuckRoller and .1385 or .125}, quaternion(Angle(0, self.SpawnYaw, 0)))
    self.NativeState = self.Native.state(self.NativeHandle)

    for i, link in ipairs(self.Render.links) do
        local e = self.Links[i]
        local fresh = not IsValid(e)
        if fresh then e = ents.Create("md_microduck_link"); self.Links[i] = e end
        assert(IsValid(e), "Could not create MicroDuck visual body " .. link.name)
        e:SetModel(link.model)
        if fresh then e:Spawn(); e:Activate(); self:DeleteOnRemove(e) end
        e:PhysicsInit(SOLID_VPHYSICS, vector_origin)
        e:SetMoveType(MOVETYPE_NONE); e:SetSolid(SOLID_VPHYSICS)
        local ph = e:GetPhysicsObject()
        if IsValid(ph) then ph:EnableMotion(false); ph:EnableGravity(false) end
        -- Render bodies remain selectable. MuJoCo owns all contact response;
        -- a second VPhysics collision response would count impacts twice.
        e:SetCustomCollisionCheck(true)
        e.MicroDuckRoot, e.MicroDuckMJRoot, e.MicroDuckBodyIndex = self, self, i
        e:SetNWEntity("MicroDuckRoot", self)
        e:SetUseType(SIMPLE_USE)
        if IsValid(self.Creator) then e:SetCreator(self.Creator) end
    end
    self:ResetControlState(true)
    self:UpdateVisuals(self.NativeState)
    self.NativeInitialized = true
    MD.Active[self] = true
end

function ENT:ResetControlState(powered)
    self.LastAction, self.Targets, self.Command, self.PendingImpulses = {}, {}, {0, 0, 0}, {}
    for i = 1, 14 do self.LastAction[i] = 0; self.Targets[i] = Render.home[i] end
    self.PhysicsRemainder, self.PolicySubstep, self.StepCount, self.ProxyClock = 0, 0, 0, 1
    self.WorldRefreshClock = 0
    Skills.reset(self)
    self:SetNWString("MicroDuckSkill", self.MicroDuckRoller and "skate" or "walk")
    self.PolicyError = nil
    self:SetNWString("MicroDuckError", "")
    self:SetNWFloat("MicroDuckRate", 1)
    self:SetPolicySteps(0); self:SetInferenceMS(0)
    self:SetMotorsEnabled(powered)
    self.Native.set_motors(self.NativeHandle, powered)
    self.NativeMotors = powered
    local r = self.NativeState.root_rotation
    Heading.reset(self, math.atan2(r[4], r[1]))
    if self.MicroDuckRoller then Roller.reset(self,math.atan2(r[4],r[1])) end
    Locomotion.reset(self, self.NativeState.root_position)
end

function ENT:UpdateVisuals(state)
    local byName = {}
    for _, b in ipairs(state.bodies) do byName[b.name] = b end
    for i, link in ipairs((self.Render or Render).links) do
        local e = self.Links[i]
        assert(IsValid(e), "MicroDuck body was removed: " .. link.name)
        local body = assert(byName[link.name], "Missing simulated body " .. link.name)
        e:SetPos(self.WorldOrigin + vec(body.com) * U)
        e:SetAngles(modelAngle(body.rotation, link.body_to_model))
    end
end

function ENT:UpdateProxies(dt)
    self.ProxyClock = self.ProxyClock + dt
    if self.ProxyClock >= .25 then
        self.ProxyClock = self.ProxyClock % .25
        local found = {}
        for _, e in ipairs(ents.FindInSphere(self:GetPos(), 120)) do
            if e ~= self and not e.MicroDuckMJRoot and e:GetSolid() ~= SOLID_NONE then
                local character = e:IsPlayer() or e:IsNPC()
                if character or (e:GetMoveType() == MOVETYPE_VPHYSICS and IsValid(e:GetPhysicsObject())) then
                    found[#found + 1] = e
                end
            end
        end
        table.sort(found, function(a, b) return a:GetPos():DistToSqr(self:GetPos()) < b:GetPos():DistToSqr(self:GetPos()) end)
        self.Proxies = {}
        for i = 1, math.min(32, #found) do self.Proxies[i] = found[i] end
    end
    local B, handle = self.Native, self.NativeHandle
    self.ProxyCenters = {}
    -- Read Source once per game tick. All fixed physics substeps use this
    -- snapshot and its measured velocities; reactions are accumulated below.
    for i = 1, 32 do
        local e = self.Proxies[i]
        if IsValid(e) and e:GetSolid() ~= SOLID_NONE then
            local lo, hi = e:OBBMins(), e:OBBMaxs()
            local center = e:LocalToWorld((lo + hi) * .5)
            local half = (hi - lo) * (.5 / U)
            half.x, half.y, half.z = math.max(half.x, .001), math.max(half.y, .001), math.max(half.z, .001)
            local character = e:IsPlayer() or e:IsNPC()
            local angle = character and Angle(0, e:GetAngles().y, 0) or e:GetAngles()
            if character then
                local offset = (lo + hi) * .5
                offset:Rotate(angle)
                center = e:GetPos() + offset
            end
            local linear, angular = e:GetVelocity() / U, Vector(0, 0, 0)
            local ph = e:GetPhysicsObject()
            if not character and IsValid(ph) then
                linear = ph:GetVelocityAtPoint(center) / U
                angular = ph:GetAngleVelocity()
                angular:Rotate(ph:GetAngles())
                angular = angular * (math.pi / 180)
            end
            B.set_proxy(handle, i, arr((center - self.WorldOrigin) / U), quaternion(angle), arr(half), true)
            B.set_proxy_velocity(handle, i, arr(linear), arr(angular))
            self.ProxyCenters[i] = center
        else
            B.set_proxy(handle, i, {0, 0, -1000}, {1, 0, 0, 0}, {.01, .01, .01}, false)
        end
    end
end

function ENT:Observe(state)
    state = state or self.NativeState
    local obs = {}
    for i = 1, 3 do obs[i] = state.gyro[i]; obs[i + 3] = state.gravity[i] end
    for i = 1, 14 do
        obs[6 + i], obs[20 + i], obs[34 + i] = state.q[i] - Render.home[i], state.qd[i], self.LastAction[i]
    end
    for i = 49, 61 do obs[i] = 0 end
    local r = state.root_rotation
    local yaw = math.atan2(r[4], r[1])
    local yawRate = r[7] * state.gyro[1] + r[8] * state.gyro[2] + r[9] * state.gyro[3]
    local command = self.Command
    if not self.MicroDuckRoller and Skills.status(self) == "walk" then
        command = Heading.update(self, H * POLICY_STEPS, command, yaw, yawRate)
        command = Locomotion.update(self, H * POLICY_STEPS, command, state.root_position, state.root_velocity, yaw)
    end
    local descriptor = self.MicroDuckRoller and Roller.update(self,H*POLICY_STEPS,command,state) or Skills.update(self, H * POLICY_STEPS, command, state)
    if descriptor.returned_to_walk then
        Heading.reset(self, yaw)
        Locomotion.reset(self, state.root_position)
    end
    for i = 1, 13 do obs[48 + i] = descriptor.command[i] end
    self.SkillDescriptor = descriptor
    self:SetNWString("MicroDuckSkill", descriptor.phase)
    self.PolicyCommand = descriptor.command
    return obs
end

function ENT:EvaluatePolicy()
    local obs = self:Observe(self.NativeState)
    local start = SysTime()
    local descriptor = self.SkillDescriptor
    local action = assert(self.Networks[descriptor.policy], "Unknown MicroDuck policy"):forward(obs)
    self:SetInferenceMS((SysTime() - start) * 1000)
    for i = 1, 14 do
        assert(finite(action[i]), "Non-finite MicroDuck neural output")
        self.LastAction[i], self.Targets[i] = action[i], Render.home[i] + action[i] * descriptor.action_scale
    end
    self.LastObservation = obs
    self.StepCount = self.StepCount + 1
    self:SetPolicySteps(self.StepCount)
end

function ENT:RequestSkill(name)
    if not self.NativeInitialized or self.PolicyError then return false, "Reset the duck before using a skill." end
    if not self:GetMotorsEnabled() then return false, "Turn the motors on first." end
    local ok, reason
    if self.MicroDuckRoller then ok,reason=Roller.request(self,name)
    else ok,reason=Skills.request(self,name) end
    if ok then self:SetNWString("MicroDuckSkill",self.MicroDuckRoller and self.MicroDuckRollerState.phase or Skills.status(self)) end
    return ok, reason
end

function ENT:RefreshWorldIfNeeded(dt)
    self.WorldRefreshClock = (self.WorldRefreshClock or 0) + dt
    if self.WorldRefreshClock < .25 then return end
    self.WorldRefreshClock = 0
    local position = self.WorldOrigin + vec(self.NativeState.root_position) * U
    if not World.needsRefresh(self.WorldMetadata, position) then return end
    local xml, metadata = World.buildXML(self.WorldOrigin, self.Runtime.base_xml, 1024, {center = position})
    assert(xml, metadata)
    self.WorldRevision = (self.WorldRevision or 0) + 1
    local name = "world_" .. self:EntIndex() .. "_" .. self.WorldRevision
    local scene, err = Runtime.writeScene(self.Runtime, name, xml)
    assert(scene, err)
    local previous = self.NativeHandle
    local snapshot = self.Native.snapshot(previous)
    local replacement = self.Native.create(scene, self.Runtime.mujoco_dll)
    local ok, failure = pcall(self.Native.restore, replacement, snapshot)
    if not ok then self.Native.destroy(replacement);error(failure) end
    self.NativeHandle = replacement
    self.Native.destroy(previous)
    if self.SceneDataPath then file.Delete(self.SceneDataPath) end
    self.SceneDataPath = self.Runtime.data_path .. "/" .. name .. ".xml"
    self.WorldMetadata = metadata
    self.NativeState = self.Native.state(replacement)
    self.WorldRefreshCount = (self.WorldRefreshCount or 0) + 1
end

-- External adapters supply SI impulses about a robot body's COM. The queue is
-- consumed exactly once over the next .005-second step, including at high tick rates.
function ENT:QueueExternalImpulse(bodyIndex, linear, angular)
    angular = angular or Vector(0, 0, 0)
    if not finite(bodyIndex) or bodyIndex % 1 ~= 0 or bodyIndex < 1 or bodyIndex > (self.MicroDuckRoller and 19 or 15) or
        not finiteVector(linear) or not finiteVector(angular) then return false end
    self.PendingImpulses = self.PendingImpulses or {}
    local pending = self.PendingImpulses[bodyIndex]
    if not pending then pending = {linear = Vector(0, 0, 0), angular = Vector(0, 0, 0)}; self.PendingImpulses[bodyIndex] = pending end
    pending.linear = pending.linear + linear
    pending.angular = pending.angular + angular
    return true
end

function ENT:GetNativeBodyIndex(part)
    if part == self then return 1 end
    if IsValid(part) and part.MicroDuckMJRoot == self then return part.MicroDuckBodyIndex end
end

function ENT:ApplyQueuedImpulses()
    for body, impulse in pairs(self.PendingImpulses) do
        self.Native.push(self.NativeHandle, body, arr(impulse.linear / H), arr(impulse.angular / H))
    end
    self.PendingImpulses = {}
end

function ENT:ApplyProxyReactions(totals)
    for index, impulse in pairs(totals) do
        local e, center = self.Proxies[index], self.ProxyCenters[index]
        if IsValid(e) and center and not e:IsPlayer() and not e:IsNPC() then
            local ph = e:GetPhysicsObject()
            if IsValid(ph) and ph:IsMotionEnabled() then
                local com = ph:LocalToWorld(ph:GetMassCenter())
                local torque = impulse.angular + ((center - com) / U):Cross(impulse.linear)
                ph:ApplyForceCenter(impulse.linear * U)
                ph:ApplyTorqueCenter(torque * (180 / math.pi))
                ph:Wake()
            end
        end
    end
end

function ENT:ControlTick(dt)
    assert(finite(dt) and dt >= 0 and dt <= .25, "Invalid MicroDuck simulation interval")
    self:RefreshWorldIfNeeded(dt)
    self:UpdateProxies(dt)
    local B, handle = self.Native, self.NativeHandle
    local motors = self:GetMotorsEnabled()
    if self.NativeMotors ~= motors then
        B.set_motors(handle, motors)
        self.NativeMotors, self.PolicySubstep = motors, 0
        local r = self.NativeState.root_rotation
        Heading.reset(self, math.atan2(r[4], r[1]))
        Locomotion.reset(self, self.NativeState.root_position)
        Skills.reset(self)
        if self.MicroDuckRoller then Roller.reset(self,math.atan2(r[4],r[1])) end
        self:SetNWString("MicroDuckSkill", self.MicroDuckRoller and "skate" or "walk")
    end
    self.PhysicsRemainder = self.PhysicsRemainder + dt
    local totals, contacts = {}, {dt = 0, overflow = 0, points = {}, proxy_impulses = {}}
    while self.PhysicsRemainder + 1e-10 >= H do
        if motors and self.PolicySubstep == 0 then self:EvaluatePolicy() end
        self:ApplyQueuedImpulses()
        local advanced = B.step(handle, H, self.Targets)
        assert(math.abs(advanced - H) < 1e-9, "MicroDuck native physics clock did not advance")
        self.NativeState = B.state(handle)
        self.Q, self.QD = self.NativeState.q, self.NativeState.qd
        local batch = B.contacts(handle)
        contacts.dt, contacts.overflow = contacts.dt + batch.dt, contacts.overflow + batch.overflow
        for _, impulse in ipairs(batch.proxy_impulses) do
            local total = totals[impulse.index]
            if not total then total = {linear = Vector(0, 0, 0), angular = Vector(0, 0, 0)}; totals[impulse.index] = total end
            total.linear, total.angular = total.linear + vec(impulse.linear), total.angular + vec(impulse.angular)
        end
        for _, point in ipairs(batch.points) do
            if #contacts.points < MAX_DETAIL_CONTACTS then contacts.points[#contacts.points + 1] = point
            else contacts.overflow = contacts.overflow + 1 end
        end
        self.PolicySubstep = (self.PolicySubstep + 1) % POLICY_STEPS
        self.PhysicsRemainder = self.PhysicsRemainder - H
    end
    self.PhysicsRemainder = math.max(0, self.PhysicsRemainder)
    for index, impulse in pairs(totals) do contacts.proxy_impulses[#contacts.proxy_impulses + 1] =
        {index = index, linear = arr(impulse.linear), angular = arr(impulse.angular)} end
    self.NativeContacts = contacts
    self:ApplyProxyReactions(totals)
    self:UpdateVisuals(self.NativeState)
end

function ENT:ReadJoints()
    if self.NativeState then return self.NativeState.q, self.NativeState.qd end
end

function ENT:ResetPose()
    local ok, err = xpcall(function()
        local rebuild = not self.NativeInitialized or not self.NativeHandle
        for i = 1, #(self.Render or Render).links do
            if not IsValid(self.Links and self.Links[i]) then rebuild = true; break end
        end
        if rebuild then self:InitializeNative(); return end
        local powered = self.PolicyError ~= nil or self:GetMotorsEnabled()
        self.Native.reset(self.NativeHandle, {0, 0, self.MicroDuckRoller and .1385 or .125}, quaternion(Angle(0, self.SpawnYaw, 0)))
        self.NativeState = self.Native.state(self.NativeHandle)
        self:ResetControlState(powered)
        self:RefreshWorldIfNeeded(.25)
        self:UpdateVisuals(self.NativeState)
        MD.Active[self] = true
    end, debug.traceback)
    if not ok then self:SetSimulationError(err) end
end

function ENT:Use(ply)
    if IsValid(ply) and ply:IsPlayer() then
        ply.MicroDuck = self
        if self.PolicyError then self:ResetPose() else self:SetMotorsEnabled(not self:GetMotorsEnabled()) end
    end
end

function ENT:ReleaseNative()
    if self.NativeHandle then
        local handle = self.NativeHandle
        self.NativeHandle = nil
        pcall(self.Native.destroy, handle)
    end
end

function ENT:OnRemove()
    MD.Active[self] = nil
    self:ReleaseNative()
    if self.SceneDataPath then file.Delete(self.SceneDataPath) end
    for _, e in ipairs(self.Links or {}) do if e ~= self and IsValid(e) then e:Remove() end end
end

hook.Add("ShouldCollide", "MicroDuckNativeContacts", function(a, b)
    if a.MicroDuckMJRoot or b.MicroDuckMJRoot then return false end
end)
hook.Add("Tick", "MicroDuckClosedLoop", function()
    for e in pairs(MD.Active) do
        if not IsValid(e) then MD.Active[e] = nil else
            local ok, err = xpcall(function() e:ControlTick(engine.TickInterval()) end, debug.traceback)
            if not ok then e:SetSimulationError(err) end
        end
    end
end)
hook.Add("ShutDown", "MicroDuckNativeCleanup", function()
    for e in pairs(MD.Active) do if IsValid(e) then e:ReleaseNative() end end
end)

local function selected(ply)
    if not IsValid(ply) then return end
    local e = ply:GetEyeTrace().Entity
    if IsValid(e) then e = e.MicroDuckRoot or e; if e:GetClass() == "md_microduck" or e:GetClass() == "md_microduck_roller" then return e end end
    if IsValid(ply.MicroDuck) then return ply.MicroDuck end
end
concommand.Add("microduck_command", function(ply, _, args)
    local e = selected(ply); if not IsValid(e) then return end
    local function number(i) local n = tonumber(args[i]); return finite(n) and n or 0 end
    e.Command = {math.Clamp(number(1), -.3, .3), math.Clamp(number(2), -.2, .2), math.Clamp(number(3), -1.5, 1.5)}
end)
concommand.Add("microduck_reset", function(ply)
    local e = selected(ply); if IsValid(e) then e:ResetPose() end
end)
concommand.Add("microduck_rate", function(ply)
    local e = selected(ply); if IsValid(e) then e:SetNWFloat("MicroDuckRate", 1) end
end)
