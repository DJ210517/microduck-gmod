ENT.Type = "anim"
ENT.Base = "base_anim"
ENT.PrintName = "MicroDuck — Real Policy"
ENT.Category = "MicroDuck"
ENT.Spawnable = true
ENT.AdminOnly = false
include("microduck/link.lua")
include("microduck/control.lua")
function ENT:SetupDataTables()
    self:NetworkVar("Bool",0,"MotorsEnabled")
    self:NetworkVar("Float",0,"InferenceMS")
    self:NetworkVar("Int",0,"PolicySteps")
end
