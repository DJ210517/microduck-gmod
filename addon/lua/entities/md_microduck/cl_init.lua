include("shared.lua")
function ENT:Draw() self:DrawModel() end
language.Add("md_microduck", "MicroDuck — Real Policy")
hook.Add("HUDPaint","MicroDuckStatus",function()
    local p=LocalPlayer()
    local e=p:GetEyeTrace().Entity
    if not IsValid(e) then return end
    e=e:GetNWEntity("MicroDuckRoot",e)
    if (e:GetClass()~="md_microduck" and e:GetClass()~="md_microduck_roller") or p:GetPos():DistToSqr(e:GetPos())>160000 then return end
    local problem=e:GetNWString("MicroDuckError","")
    draw.SimpleText("MICRODUCK  |  "..(problem~="" and problem or (e:GetMotorsEnabled() and "NEURAL POLICY" or "MOTORS OFF")),"Trebuchet24",ScrW()/2,ScrH()/2+70,Color(255,200,60),TEXT_ALIGN_CENTER)
    local weapon=p:GetActiveWeapon()
    local instructions="E: motors  •  microduck_command <forward> <left> <turn>  •  microduck_reset"
    if IsValid(weapon) and weapon:GetClass()=="weapon_microduck_remote" then instructions="Left-click: drive  •  Right-click: motors  •  R: reset" end
    draw.SimpleText(instructions,"DermaDefault",ScrW()/2,ScrH()/2+98,color_white,TEXT_ALIGN_CENTER)
    draw.SimpleText(string.format("%d policy steps  |  %.2f ms inference",e:GetPolicySteps(),e:GetInferenceMS()),"DermaDefault",ScrW()/2,ScrH()/2+116,color_white,TEXT_ALIGN_CENTER)
end)
