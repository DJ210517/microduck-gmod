-- Translate a Source damage impulse into the robot's physical solver.
-- The policy receives the resulting body motion on its next observation.
hook.Add("EntityTakeDamage","MicroDuckNativeDamage",function(part,damage)
    local root=part.MicroDuckMJRoot
    if not IsValid(root) or not root.NativeHandle or not root.QueueExternalImpulse then return end
    local body=part.MicroDuckBodyIndex or 1
    local impulse=damage:GetDamageForce()/39.37007874015748
    local point=damage:GetDamagePosition()
    if point==vector_origin then point=part:GetPos() end
    local lever=(point-part:GetPos())/39.37007874015748
    root:QueueExternalImpulse(body,impulse,lever:Cross(impulse))
end)

-- Source's physgun cannot move individual render pieces independently of the
-- native articulated robot. Pushing props and applying damage remain physical.
hook.Add("PhysgunPickup","MicroDuckNativePickup",function(_,part)
    if part.MicroDuckMJRoot then return false end
end)
hook.Add("GravGunPickupAllowed","MicroDuckNativePickup",function(_,part)
    if part.MicroDuckMJRoot then return false end
end)
