local LINK={Type="anim",Base="base_anim",PrintName="MicroDuck link",Spawnable=false}
function LINK:Draw() self:DrawModel() end
function LINK:Use(p)
    local root=self:GetNWEntity("MicroDuckRoot")
    if IsValid(root) then root:Use(p) end
end
scripted_ents.Register(LINK,"md_microduck_link")
