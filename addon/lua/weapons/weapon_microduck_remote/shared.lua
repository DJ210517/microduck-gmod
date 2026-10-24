if SERVER then AddCSLuaFile() end

SWEP.Base="weapon_base"
SWEP.PrintName="MicroDuck Remote"
SWEP.Category="MicroDuck"
SWEP.Author="MicroDuck GMod port"
SWEP.Instructions="Left-click: drive. Shift+E: player/chase view. Right-click: motors. Shift+left/right click: kicks. E: sit/stand or crouch. F: roll. R: reset. Space: return."
SWEP.Spawnable=true
SWEP.AdminOnly=false
SWEP.UseHands=true
SWEP.ViewModel="models/weapons/c_pistol.mdl"
SWEP.WorldModel="models/weapons/w_pistol.mdl"
SWEP.ViewModelFOV=54
SWEP.HoldType="pistol"
SWEP.Slot=0
SWEP.SlotPos=5
SWEP.DrawAmmo=false
SWEP.DrawCrosshair=true
SWEP.Primary={ClipSize=-1,DefaultClip=-1,Automatic=false,Ammo="none"}
SWEP.Secondary={ClipSize=-1,DefaultClip=-1,Automatic=false,Ammo="none"}

local function duck(part)
    if not IsValid(part) then return end
    local e=part.MicroDuckRoot or part:GetNWEntity("MicroDuckRoot",part)
    if IsValid(e) and (e:GetClass()=="md_microduck" or e:GetClass()=="md_microduck_roller") then return e end
end

function SWEP:Initialize() self:SetHoldType("pistol") end

function SWEP:TargetDuck()
    local p=self:GetOwner()
    if not IsValid(p) then return end
    local e=duck(p:GetEyeTrace().Entity)
    if not IsValid(e) then
        -- A small aiming tolerance makes the real-size duck easy to select.
        local tr=util.TraceHull({start=p:GetShootPos(),endpos=p:GetShootPos()+p:GetAimVector()*2048,
            mins=Vector(-2,-2,-2),maxs=Vector(2,2,2),filter=p,mask=MASK_SHOT})
        e=duck(tr.Entity)
    end
    if not IsValid(e) then e=duck(self:GetNWEntity("MicroDuckPaired")) end
    if not IsValid(e) then e=duck(p.MicroDuck) end
    if IsValid(e) then
        self:SetNWEntity("MicroDuckPaired",e)
        return e
    end
end

function SWEP:PrimaryAttack()
    self:SetNextPrimaryFire(CurTime()+.35)
    if CLIENT then return end
    local p=self:GetOwner()
    if not IsValid(p) then return end
    if IsValid(p:GetNWEntity("MicroDuckControl")) then self:StopRemote();return end
    local e=self:TargetDuck()
    if not IsValid(e) then
        p:ChatPrint("Aim at a MicroDuck and left-click. Spawn one from Entities > MicroDuck.")
        self:EmitSound("buttons/button10.wav",55,110)
        return
    end
    local ok,reason=MicroDuck.StartControl(p,e,self)
    if ok then
        self.ControlOwner=p
        self:EmitSound("buttons/button14.wav",55,120)
    elseif reason then p:ChatPrint(reason) end
end

function SWEP:SecondaryAttack()
    self:SetNextSecondaryFire(CurTime()+.35)
    if CLIENT then return end
    local e=self:TargetDuck()
    if IsValid(e) then
        e:SetMotorsEnabled(not e:GetMotorsEnabled())
        self:EmitSound("buttons/button14.wav",55,e:GetMotorsEnabled() and 120 or 85)
    end
end

function SWEP:RequestAction(name)
    if CLIENT then return end
    local p=self:GetOwner()
    if not IsValid(p) then return end
    local e=p:GetNWEntity("MicroDuckControl")
    if not IsValid(e) then e=self:TargetDuck() end
    if not IsValid(e) then p:ChatPrint("Aim at a MicroDuck to select it first.");return end
    if IsValid(e.MicroDuckController) and e.MicroDuckController~=p then
        p:ChatPrint("That duck is already being controlled.");return
    end
    local ok,reason=e:RequestSkill(name)
    if ok then self:EmitSound("buttons/button14.wav",55,120)
    elseif reason then p:ChatPrint(reason) end
end

function SWEP:Reload()
    if CLIENT or self.ResetDown then return end
    self.ResetDown=true
    local e=self:TargetDuck()
    if IsValid(e) then e:ResetPose() end
end

function SWEP:Think()
    if CLIENT then return end
    local p=self:GetOwner()
    if not IsValid(p) or not p:KeyDown(IN_RELOAD) then self.ResetDown=false end
end

function SWEP:StopRemote()
    if CLIENT then return end
    local p=self.ControlOwner
    if not IsValid(p) then p=self:GetOwner() end
    if IsValid(p) and p.MicroDuckRemoteWeapon==self then MicroDuck.StopControl(p) end
    self.ControlOwner=nil
end
function SWEP:Holster() self:StopRemote();return true end
function SWEP:OnDrop() self:StopRemote() end
function SWEP:OnRemove() self:StopRemote() end
function SWEP:OwnerChanged() self:StopRemote() end

if CLIENT then
    local hudScale
    function SWEP:DrawHUD()
        local p=LocalPlayer()
        if IsValid(p:GetNWEntity("MicroDuckControl")) then return end
        local paired=self:GetNWEntity("MicroDuckPaired")
        local roller=IsValid(paired) and paired:GetNWBool('MicroDuckRoller',false)
        local title=IsValid(paired) and "MICRODUCK REMOTE · LINKED" or "MICRODUCK REMOTE"
        local scale=math.Clamp(ScrH()/1080,1,2)
        if hudScale~=scale then
            hudScale=scale
            surface.CreateFont("MicroDuckRemoteTitle",{font="Trebuchet MS",size=24*scale,weight=700})
            surface.CreateFont("MicroDuckRemoteText",{font="Tahoma",size=14*scale,weight=500})
        end
        local width,height=530*scale,152*scale
        local x,y=(ScrW()-width)*.5,ScrH()-height-36*scale
        draw.RoundedBox(6*scale,x,y,width,height,Color(15,20,25,220))
        draw.SimpleText(title,"MicroDuckRemoteTitle",ScrW()*.5,y+10*scale,Color(255,195,50),TEXT_ALIGN_CENTER)
        draw.SimpleText("Left-click: select / drive duck","MicroDuckRemoteText",ScrW()*.5,y+40*scale,color_white,TEXT_ALIGN_CENTER)
        draw.SimpleText("Right-click: motors   |   R: reset paired duck","MicroDuckRemoteText",ScrW()*.5,y+59*scale,Color(185,205,215),TEXT_ALIGN_CENTER)
        draw.SimpleText(roller and "Roller duck: E crouch glide" or "E: sit / stand   |   F: forward roll","MicroDuckRemoteText",ScrW()*.5,y+80*scale,color_white,TEXT_ALIGN_CENTER)
        draw.SimpleText(roller and "W push  |  S brake  |  A/D steer" or "Shift + left / right click: left / right kick","MicroDuckRemoteText",ScrW()*.5,y+101*scale,color_white,TEXT_ALIGN_CENTER)
        draw.SimpleText(p:GetNWBool("MicroDuckPlayerView",false) and "Player view selected  |  Shift + E: chase camera" or "Chase camera selected  |  Shift + E: player view","MicroDuckRemoteText",ScrW()*.5,y+122*scale,Color(255,215,110),TEXT_ALIGN_CENTER)
    end
end
