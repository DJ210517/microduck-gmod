-- Export the actual closed convex solids of the Source world physics object.
-- No traces, artificial slabs, or support planes are used. Small maps export
-- every available solid; larger maps use an explicitly reported bounded area.
local W = {}
local U = 100 / 2.54
local ASSET_MARKER = "<!--MICRODUCK_WORLD_ASSETS-->"
local WORLD_MARKER = "<!--MICRODUCK_WORLD_GEOMS-->"
local function number(x) return string.format("%.12g", x) end
local function xyz(v) return number(v.x) .. " " .. number(v.y) .. " " .. number(v.z) end
local function finiteNumber(x) return type(x) == "number" and x == x and math.abs(x) < 1e8 end
local function finite(v) return v and finiteNumber(v.x) and finiteNumber(v.y) and finiteNumber(v.z) end
local function array(v) return {v.x, v.y, v.z} end
local function limits(lo, hi, p)
    lo.x, lo.y, lo.z = math.min(lo.x, p.x), math.min(lo.y, p.y), math.min(lo.z, p.z)
    hi.x, hi.y, hi.z = math.max(hi.x, p.x), math.max(hi.y, p.y), math.max(hi.z, p.z)
end
local function bounds()
    return Vector(math.huge, math.huge, math.huge), Vector(-math.huge, -math.huge, -math.huge)
end
local function positiveInteger(value, default, maximum)
    value = value == nil and default or value
    if not finiteNumber(value) or value < 1 or value > maximum or value % 1 ~= 0 then return nil end
    return value
end

local function collectObjects(world)
    local result, seen = {}, {}
    local function add(ph)
        if IsValid(ph) and not seen[ph] then seen[ph] = true; result[#result + 1] = ph end
    end
    -- World:GetPhysicsObjectCount() returns zero on gm_flatgrass even though
    -- its primary physics object exists and contains all 112 brush solids.
    if world.GetPhysicsObject then add(world:GetPhysicsObject()) end
    local count = world.GetPhysicsObjectCount and world:GetPhysicsObjectCount() or 0
    if count > 512 then return nil, "World reports too many physics objects" end
    if world.GetPhysicsObjectNum then
        for index = 0, count - 1 do add(world:GetPhysicsObjectNum(index)) end
    end
    return result, nil, count
end

local function readConvex(raw, ph, objectIndex, convexIndex)
    if type(raw) ~= "table" or #raw < 12 or #raw % 3 ~= 0 then
        return nil, "World physics returned an incomplete convex triangle mesh"
    end
    local vertices, triangles, keys = {}, {}, {}
    local lo, hi = bounds()
    for _, entry in ipairs(raw) do
        local p = entry.pos
        if not finite(p) then return nil, "World convex contains a non-finite vertex" end
        -- PhysObj mesh vertices are local to that object's physical transform.
        p = ph:LocalToWorld(p)
        if not finite(p) then return nil, "World convex transform is non-finite" end
        local key = xyz(p)
        local index = keys[key]
        if not index then
            index = #vertices + 1
            keys[key] = index
            vertices[index] = Vector(p.x, p.y, p.z)
            limits(lo, hi, p)
        end
        triangles[#triangles + 1] = index
    end
    if #vertices < 4 then return nil, "World convex has fewer than four distinct vertices" end
    local center = (lo + hi) * .5
    local volume6 = 0
    for i = 1, #triangles, 3 do
        local a = vertices[triangles[i]] - center
        local b = vertices[triangles[i + 1]] - center
        local c = vertices[triangles[i + 2]] - center
        volume6 = volume6 + a:Dot(b:Cross(c))
    end
    if math.abs(volume6) < 1e-6 then return nil, "World convex has no solid volume" end
    return {vertices = vertices, lo = lo, hi = hi, object_index = objectIndex,
        source_index = convexIndex, triangles = #raw / 3, volume = math.abs(volume6) / 6}
end

local function intersects(solid, lo, hi)
    return solid.lo.x <= hi.x and solid.hi.x >= lo.x and
        solid.lo.y <= hi.y and solid.hi.y >= lo.y and
        solid.lo.z <= hi.z and solid.hi.z >= lo.z
end

local function solidXML(solid, origin, index)
    local coordinates = {}
    for _, p in ipairs(solid.vertices) do coordinates[#coordinates + 1] = xyz((p - origin) / U) end
    local name = "md_world_solid_" .. index
    -- GetMeshConvexes already supplies convex solids. MuJoCo reconstructs each
    -- hull from the unchanged vertices; omitting faces avoids winding changes.
    return '<mesh name="' .. name .. '" vertex="' .. table.concat(coordinates, " ") .. '"/>',
        '<geom name="' .. name .. '" type="mesh" mesh="' .. name ..
        '" contype="1" conaffinity="1" friction="1 .005 .0001" margin="0" group="4"/>'
end

function W.export(origin, radius, options)
    options = options or {}
    radius = radius or 1024
    if not finite(origin) or not finiteNumber(radius) or radius <= 0 or radius > 32768 then
        return nil, "Invalid world origin/radius"
    end
    local center = options.center or origin
    if not finite(center) then return nil, "Invalid world coverage center" end
    local maximum = positiveInteger(options.maxConvexes, 4096, 16384)
    local vertexLimit = positiveInteger(options.maxVertices, 200000, 1000000)
    local scanLimit = positiveInteger(options.maxScanVertices, 2000000, 8000000)
    local depth = options.depth or math.max(radius, 4096)
    local height = options.height or radius
    if not maximum or not vertexLimit or not scanLimit or not finiteNumber(depth) or depth <= 0 or
        depth > 65536 or not finiteNumber(height) or height <= 0 or height > 32768 then
        return nil, "Invalid world export limits"
    end
    local world = game.GetWorld()
    -- IsValid(worldspawn) is false by design; test its identity instead.
    if not world or not world.IsWorld or not world:IsWorld() then return nil, "World entity is unavailable" end
    local objects, objectError, reportedCount = collectObjects(world)
    if not objects then return nil, objectError end
    if #objects == 0 then return nil, "World has no accessible collision physics object" end
    -- Selection can move while MuJoCo coordinates retain their original anchor.
    local queryLo, queryHi = center - Vector(radius, radius, depth), center + Vector(radius, radius, height)
    local meta = {source = "world_physics_convexes", units_per_m = U, origin = array(origin),
        radius = radius, downward_range = depth, upward_range = height,
        coverage_center = array(center), full_world = false,
        query_min = array(queryLo), query_max = array(queryHi),
        physics_objects = #objects, reported_physics_object_count = reportedCount,
        source_convexes = 0, source_vertices = 0, source_triangles = 0,
        candidates = 0, exported = 0, exported_vertices = 0, outside_radius = 0,
        maximum_convexes = maximum, maximum_vertices = vertexLimit, truncated = false,
        displacements_verified = false, static_props_included = false,
        limitations = {"Coverage includes only solids exposed by world physics objects",
            "Static prop collision is supplied separately", "Displacement coverage has not been verified"}, solids = {}}
    local all, nearby = {}, {}
    local allVertices, nearVertices, scanned = 0, 0, 0
    local mapLo, mapHi = bounds()
    for objectIndex, ph in ipairs(objects) do
        if not ph.GetMeshConvexes or not ph.LocalToWorld then return nil, "World collision mesh API is unavailable", meta end
        local ok, raw = pcall(ph.GetMeshConvexes, ph)
        if not ok or type(raw) ~= "table" then return nil, "Could not read world collision convexes", meta end
        for convexIndex, mesh in ipairs(raw) do
            scanned = scanned + #mesh
            if scanned > scanLimit then return nil, "World collision source exceeds scan vertex limit", meta end
            local solid, err = readConvex(mesh, ph, objectIndex, convexIndex)
            if not solid then return nil, err .. " (object " .. objectIndex .. ", convex " .. convexIndex .. ")", meta end
            all[#all + 1] = solid
            allVertices = allVertices + #solid.vertices
            meta.source_triangles = meta.source_triangles + solid.triangles
            limits(mapLo, mapHi, solid.lo); limits(mapLo, mapHi, solid.hi)
            if intersects(solid, queryLo, queryHi) then
                nearby[#nearby + 1] = solid
                nearVertices = nearVertices + #solid.vertices
            end
        end
    end
    meta.source_convexes, meta.source_vertices, meta.candidates = #all, allVertices, #nearby
    meta.outside_radius = #all - #nearby
    if #all == 0 then return nil, "World physics returned no collision solids", meta end
    local wholeMapFits = #all <= maximum and allVertices <= vertexLimit
    local useAll = options.fullWorld ~= false and wholeMapFits
    if options.fullWorld == true and not wholeMapFits then return nil, "Whole-world collision export exceeds configured limits", meta end
    local selected = useAll and all or nearby
    local selectedVertices = useAll and allVertices or nearVertices
    if #selected > maximum or selectedVertices > vertexLimit then
        -- Never silently truncate a neighborhood: that would create missing
        -- floors. The caller receives an explicit failure and can change scope.
        return nil, "Collision neighborhood exceeds configured export limits", meta
    end
    if #selected == 0 then return nil, "No world collision solids intersect the requested area", meta end
    meta.coverage_mode = useAll and "world" or "bounded"
    meta.full_world = useAll
    meta.all_available_world_solids = useAll
    meta.coverage_min = array(useAll and mapLo or queryLo)
    meta.coverage_max = array(useAll and mapHi or queryHi)
    meta.refresh_required_outside_bounds = not useAll
    local assets, geoms = {}, {}
    for index, solid in ipairs(selected) do
        local asset, geom = solidXML(solid, origin, index)
        assets[#assets + 1], geoms[#geoms + 1] = asset, geom
        meta.solids[index] = {object_index = solid.object_index, source_index = solid.source_index,
            minimum = array(solid.lo), maximum = array(solid.hi), vertices = #solid.vertices,
            triangles = solid.triangles, volume_source_units = solid.volume}
    end
    meta.exported, meta.exported_vertices = #selected, selectedVertices
    return table.concat(assets, "\n"), table.concat(geoms, "\n"), meta
end

function W.needsRefresh(meta, position)
    if not meta or not finite(position) then return true end
    if meta.full_world then return false end
    local center = meta.coverage_center
    if not center or not meta.radius then return true end
    -- Refresh at half the horizontal radius, also after that much vertical
    -- travel. This leaves a large overlap during a fall instead of waiting
    -- until the lower coverage plane has already been crossed.
    local horizontal = meta.radius * .5
    local below = math.min((meta.downward_range or meta.radius) * .5, horizontal)
    local above = math.min((meta.upward_range or meta.radius) * .5, horizontal)
    return math.abs(position.x - center[1]) >= horizontal or
        math.abs(position.y - center[2]) >= horizontal or
        position.z - center[3] <= -below or position.z - center[3] >= above
end

local function replaceOnce(text, marker, replacement)
    local first, last = string.find(text, marker, 1, true)
    if not first then return nil end
    return string.sub(text, 1, first - 1) .. replacement .. string.sub(text, last + 1)
end
function W.buildXML(origin, baseXML, radius, options)
    if type(baseXML) ~= "string" then return nil, "Missing base XML" end
    local assets, geoms, meta = W.export(origin, radius, options)
    if not assets then return nil, geoms, meta end
    local xml = replaceOnce(baseXML, ASSET_MARKER, assets)
    if not xml then return nil, "Missing world asset marker", meta end
    xml = replaceOnce(xml, WORLD_MARKER, geoms)
    if not xml then return nil, "Missing world geom marker", meta end
    return xml, meta
end
W.units_per_m = U
return W
