if SERVER then
    MicroDuck=MicroDuck or {}
    local MD=MicroDuck
    function MD.SetPlayerView(p,enabled)
        if not IsValid(p) then return false end
        p:SetNWBool("MicroDuckPlayerView",enabled==true)
        return true
    end
    function MD.ToggleView(p)
        if not IsValid(p) then return false end
        MD.SetPlayerView(p,not p:GetNWBool("MicroDuckPlayerView",false))
        p:ChatPrint(p:GetNWBool("MicroDuckPlayerView",false) and "MicroDuck: player view. WASD drives the duck; Space returns control to you." or "MicroDuck: chase camera.")
        return true
    end
    function MD.StopControl(p)
        if not IsValid(p) then return end
        local e=p:GetNWEntity("MicroDuckControl")
        if IsValid(e) then
            e.Command={0,0,0}
            if e.MicroDuckController==p then e.MicroDuckController=nil end
        end
        p:SetNWEntity("MicroDuckControl",NULL)
        p.MicroDuckRemoteWeapon=nil
        p.MicroDuckResetDown=nil
        p.MicroDuckMotorDown=nil
        p.MicroDuckSitDown=nil
        p.MicroDuckLeftKickDown=nil
        p.MicroDuckRightKickDown=nil
    end
    function MD.StartControl(p,e,remote)
        if not IsValid(p) or not p:Alive() or not IsValid(e) or (e:GetClass()~="md_microduck" and e:GetClass()~="md_microduck_roller") then return false end
        if IsValid(e.MicroDuckController) and e.MicroDuckController~=p then
            return false,"That duck is already being controlled."
        end
        MD.StopControl(p)
        e.Command={0,0,0}
        e.MicroDuckController=p
        p.MicroDuck=e
        p.MicroDuckRemoteWeapon=remote
        p:SetNWEntity("MicroDuckControl",e)
        return true
    end
    local function selected(p)
        if not IsValid(p) then return end
        local e=p:GetEyeTrace().Entity
        if IsValid(e) then e=e.MicroDuckRoot or e; if e:GetClass()=="md_microduck" or e:GetClass()=="md_microduck_roller" then return e end end
        if IsValid(p.MicroDuck) then return p.MicroDuck end
    end
    concommand.Add("microduck_control",function(p)
        local current=p:GetNWEntity("MicroDuckControl")
        if IsValid(current) then
            MD.StopControl(p)
        else
            local e=selected(p)
            if IsValid(e) then
                local ok,reason=MD.StartControl(p,e)
                if not ok and reason then p:ChatPrint(reason) end
            end
        end
    end)
    concommand.Add("microduck_motors",function(p)
        local e=selected(p); if IsValid(e) then e:SetMotorsEnabled(not e:GetMotorsEnabled()) end
    end)
    concommand.Add("microduck_view",function(p,_,args)
        if not IsValid(p) then return end
        local mode=string.lower(args[1] or "toggle")
        if mode=="toggle" then MD.ToggleView(p)
        elseif mode=="player" then MD.SetPlayerView(p,true)
        elseif mode=="chase" then MD.SetPlayerView(p,false)
        else p:ChatPrint("microduck_view player | chase | toggle") end
    end)
    concommand.Add("microduck_spawn",function(p)
        if not IsValid(p) then return end
        local point=p:GetPos()+p:GetForward()*65
        local tr=util.TraceLine({start=point+Vector(0,0,100),endpos=point-Vector(0,0,500),filter=p})
        if not tr.Hit then return end
        scripted_ents.GetStored("md_microduck").t:SpawnFunction(p,tr)
    end)
    hook.Add("StartCommand","MicroDuckRemote",function(p,cmd)
        local b=cmd:GetButtons()
        local function pressed(k) return bit.band(b,k)~=0 and 1 or 0 end
        local weapon=p.GetActiveWeapon and p:GetActiveWeapon()
        local remote=IsValid(weapon) and weapon:GetClass()=="weapon_microduck_remote"
        local kickModifier=remote and pressed(IN_SPEED)==1
        if remote then
            local left=kickModifier and pressed(IN_ATTACK)==1
            local right=kickModifier and pressed(IN_ATTACK2)==1
            -- Consume modified attacks in both camera modes so they cannot
            -- also toggle drive/power. Holding a button never repeats a kick.
            if left and not p.MicroDuckLeftKickConsumed then weapon:RequestAction("kick_left") end
            if right and not p.MicroDuckRightKickConsumed then weapon:RequestAction("kick_right") end
            p.MicroDuckLeftKickDown,p.MicroDuckRightKickDown=left,right
            if pressed(IN_ATTACK)==0 then p.MicroDuckLeftKickConsumed=nil
            elseif left then p.MicroDuckLeftKickConsumed=true end
            if pressed(IN_ATTACK2)==0 then p.MicroDuckRightKickConsumed=nil
            elseif right then p.MicroDuckRightKickConsumed=true end
            -- Releasing Shift before the mouse must not turn the remainder of
            -- the same click into an ordinary drive or motor-power click.
            if p.MicroDuckLeftKickConsumed then cmd:RemoveKey(IN_ATTACK) end
            if p.MicroDuckRightKickConsumed then cmd:RemoveKey(IN_ATTACK2) end
            local sit=pressed(IN_USE)==1
            if sit and not p.MicroDuckSitDown then
                if kickModifier then MD.ToggleView(p) else weapon:RequestAction("toggle_sit") end
            end
            p.MicroDuckSitDown=sit
            if sit then cmd:RemoveKey(IN_USE) end
            if cmd:GetImpulse()==100 then weapon:RequestAction("roll");cmd:SetImpulse(0) end
        else
            p.MicroDuckSitDown=nil;p.MicroDuckLeftKickDown=nil;p.MicroDuckRightKickDown=nil
            p.MicroDuckLeftKickConsumed=nil;p.MicroDuckRightKickConsumed=nil
        end
        local e=p:GetNWEntity("MicroDuckControl")
        if not IsValid(e) then return end
        if not p:Alive() then MD.StopControl(p);return end
        if e.MicroDuckRoller then
            e.Command={.6*pressed(IN_FORWARD)-.5*pressed(IN_BACK),0,.7*(pressed(IN_MOVELEFT)-pressed(IN_MOVERIGHT))}
        else
            e.Command={.3*(pressed(IN_FORWARD)-pressed(IN_BACK)),.15*(pressed(IN_LEFT)-pressed(IN_RIGHT)),.7*(pressed(IN_MOVELEFT)-pressed(IN_MOVERIGHT))}
        end
        local reset=pressed(IN_RELOAD)==1
        if reset and not p.MicroDuckResetDown then e:ResetPose() end
        p.MicroDuckResetDown=reset
        if IsValid(p.MicroDuckRemoteWeapon) then
            local power=pressed(IN_ATTACK2)==1 and not p.MicroDuckRightKickConsumed
            if power and not p.MicroDuckMotorDown then e:SetMotorsEnabled(not e:GetMotorsEnabled()) end
            p.MicroDuckMotorDown=power
        end
        if pressed(IN_JUMP)==1 then
            MD.StopControl(p)
        end
        cmd:ClearMovement(); cmd:ClearButtons()
    end)
    hook.Add("PlayerDeath","MicroDuckControl",function(p) MD.StopControl(p) end)
    hook.Add("PlayerDisconnected","MicroDuckControl",function(p) MD.StopControl(p) end)
    hook.Add("EntityRemoved","MicroDuckControl",function(e)
        if (e:GetClass()=="md_microduck" or e:GetClass()=="md_microduck_roller") and IsValid(e.MicroDuckController) then MD.StopControl(e.MicroDuckController) end
    end)
else
    local camera={}
    local function chaseView(p)
        return IsValid(p:GetNWEntity("MicroDuckControl")) and not p:GetNWBool("MicroDuckPlayerView",false)
    end
    hook.Add("SetupMove","MicroDuckRemote",function(p,movement)
        if not IsValid(p:GetNWEntity("MicroDuckControl")) then return end
        -- Match the server's stationary-player movement prediction without
        -- clearing the UserCmd that carries the duck's input to the server.
        movement:SetForwardSpeed(0);movement:SetSideSpeed(0);movement:SetUpSpeed(0);movement:SetButtons(0)
    end)
    hook.Add("CalcView","MicroDuckRemote",function(p)
        local e=p:GetNWEntity("MicroDuckControl")
        if not chaseView(p) then camera.entity=nil; return end
        local eye=p:EyeAngles()
        if camera.entity~=e then
            camera={entity=e,yaw=e:GetNWFloat("MicroDuckHeading",0)-40,pitch=18,last=Angle(eye.p,eye.y,0)}
        else
            camera.yaw=camera.yaw-math.AngleDifference(eye.y,camera.last.y)
            camera.pitch=math.Clamp(camera.pitch+math.AngleDifference(eye.p,camera.last.p),-10,75)
            camera.last=Angle(eye.p,eye.y,0)
        end
        local focus=e:GetPos()+Vector(0,0,1.5)
        local direction=Angle(-camera.pitch,camera.yaw,0):Forward()
        local origin=focus+direction*34
        local tr=util.TraceHull({start=focus,endpos=origin,mins=Vector(-.3,-.3,-.3),maxs=Vector(.3,.3,.3),filter=function(ent)
            return ent~=p and ent~=e and ent:GetNWEntity("MicroDuckRoot")~=e
        end})
        if tr.Hit then origin=tr.HitPos+tr.HitNormal*.5 end
        return {origin=origin,angles=(focus-origin):Angle(),fov=48,drawviewer=false}
    end)
    local hudScale
    local function updateFonts()
        local scale=math.Clamp(ScrH()/1080,1,2)
        if hudScale~=scale then
            hudScale=scale
            surface.CreateFont("MicroDuckTitle",{font="Trebuchet MS",size=24*scale,weight=700})
            surface.CreateFont("MicroDuckText",{font="Tahoma",size=14*scale,weight=500})
        end
        return scale
    end
    hook.Add("HUDPaint","MicroDuckRemote",function()
        local e=LocalPlayer():GetNWEntity("MicroDuckControl")
        if not IsValid(e) then return end
        local s=updateFonts()
        draw.RoundedBox(6*s,20*s,20*s,530*s,184*s,Color(15,20,25,220))
        local roller=e:GetNWBool('MicroDuckRoller',false)
        draw.SimpleText(roller and "MICRODUCK · REAL ROLLER POLICY" or "MICRODUCK · REAL NEURAL POLICY","MicroDuckTitle",32*s,30*s,Color(255,195,50))
        draw.SimpleText(roller and "W: push  |  S: brake  |  A/D: steer" or "W/S forward/back  |  A/D turn  |  arrows strafe","MicroDuckText",32*s,60*s,color_white)
        local remote=LocalPlayer():GetActiveWeapon()
        local playerView=LocalPlayer():GetNWBool("MicroDuckPlayerView",false)
        local mouse=playerView and "Mouse: look" or "Mouse: orbit"
        local instructions=mouse.."  |  R: reset pose  |  Space: return"
        if IsValid(remote) and remote:GetClass()=="weapon_microduck_remote" then instructions=mouse.."  |  R: reset  |  RMB: power  |  Space: return" end
        draw.SimpleText(instructions,"MicroDuckText",32*s,79*s,color_white)
        if IsValid(remote) and remote:GetClass()=="weapon_microduck_remote" then
            draw.SimpleText(roller and "E: crouch glide" or "E: sit / stand  |  F: forward roll","MicroDuckText",32*s,99*s,color_white)
            draw.SimpleText(roller and "Release W: coast  |  S: brake to a stop" or "Shift + LMB / RMB: left / right kick","MicroDuckText",32*s,119*s,color_white)
        end
        draw.SimpleText(playerView and "Player view  |  Shift + E: chase camera" or "Chase camera  |  Shift + E: player view","MicroDuckText",32*s,139*s,Color(255,215,110))
        local problem=e:GetNWString("MicroDuckError","")
        local phase=e:GetNWString("MicroDuckSkill","walk")
        local names={walk="walking",sit="sitting down",hold="seated",rise="standing up",roll="forward roll",kick_left="left kick",kick_right="right kick",recover="recovering",skate="skating",crouch="crouch glide",roller_recover="roller recovery"}
        local status=problem~="" and ("Stopped: "..problem) or string.format("%s  |  %s  |  %d neural steps",names[phase] or phase,e:GetMotorsEnabled() and "motors on" or "motors off",e:GetPolicySteps())
        draw.SimpleText(status,"MicroDuckText",32*s,167*s,problem~="" and Color(255,130,100) or Color(185,205,215))
    end)
    local hidden={CHudHealth=true,CHudBattery=true,CHudAmmo=true,CHudSecondaryAmmo=true,CHudCrosshair=true}
    hook.Add("HUDShouldDraw","MicroDuckRemote",function(name)
        if hidden[name] and chaseView(LocalPlayer()) then return false end
    end)
    hook.Add("ShouldDrawLocalPlayer","MicroDuckRemote",function()
        if chaseView(LocalPlayer()) then return false end
    end)
    hook.Add("PreDrawViewModel","MicroDuckRemote",function()
        if chaseView(LocalPlayer()) then return true end
    end)
end
