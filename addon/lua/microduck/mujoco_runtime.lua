-- Materialize mounted MJCF/mesh assets for the native MuJoCo file loader.
-- No DLL loading or filesystem work occurs until prepare() is called.
local R = {}
local SOURCE = "data_static/microduck_mj/"
local cache = {}

local function normalize(path)
    return type(path) == "string" and string.gsub(string.gsub(path, "\\", "/"), "/+$", "") or nil
end
local function safeRelative(path)
    return type(path) == "string" and string.match(path, "^[a-z0-9_./-]+$") and
        string.sub(path, 1, 1) ~= "/" and not string.find(path, "..", 1, true)
end

function R.prepare(paths, variant)
    local source=variant=='roller' and 'data_static/microduck_mj_roller/' or SOURCE
    if type(paths) ~= "table" then return nil, "Missing native MicroDuck runtime paths" end
    local dataDir = normalize(paths.data_dir or (paths.game_dir and paths.game_dir .. "/data"))
    local dll = normalize(paths.mujoco_dll or (paths.game_dir and paths.game_dir .. "/lua/bin/mujoco.dll"))
    if not dataDir or not dll then return nil, "Missing absolute data directory or MuJoCo DLL path" end
    local raw = file.Read(source .. "manifest.json", "GAME")
    local manifest = raw and util.JSONToTable(raw)
    if not manifest or manifest.schema_version ~= 1 or type(manifest.files) ~= "table" or
        type(manifest.content_id) ~= "string" or not string.match(manifest.content_id, "^[a-f0-9]+$") then
        return nil, "Missing or unsupported MicroDuck physics asset manifest"
    end
    local key = dataDir .. "/" .. manifest.content_id
    if cache[key] then return cache[key] end
    local dataPath = "microduck_mj/" .. manifest.content_id
    file.CreateDir(dataPath)
    for _, entry in ipairs(manifest.files) do
        if not safeRelative(entry.path) then return nil, "Invalid runtime asset path" end
        local target = dataPath .. "/" .. entry.path
        local content = file.Read(target, "DATA")
        if not content or util.SHA256(content) ~= entry.sha256 then
            content = file.Read(source .. entry.path, "GAME")
            if not content or #content ~= entry.bytes or util.SHA256(content) ~= entry.sha256 then
                return nil, "Missing or damaged MicroDuck physics asset: " .. entry.path
            end
            local parent = string.match(target, "^(.*)/[^/]+$")
            if parent then file.CreateDir(parent) end
            if not file.Write(target, content) then return nil, "Could not write physics asset: " .. target end
            local saved = file.Read(target, "DATA")
            if not saved or util.SHA256(saved) ~= entry.sha256 then
                return nil, "Physics asset verification failed: " .. target
            end
        end
    end
    local base = file.Read(dataPath .. "/base.xml", "DATA")
    if not base then return nil, "Prepared MicroDuck scene is missing" end
    local ready = {base_xml = base, data_path = dataPath, absolute_directory = dataDir .. "/" .. dataPath,
        mujoco_dll = dll, manifest = manifest}
    cache[key] = ready
    return ready
end

function R.writeScene(ready, name, xml)
    if type(ready) ~= "table" or not safeRelative(ready.data_path) then return nil, "Runtime was not prepared" end
    if type(name) ~= "string" or not string.match(name, "^[a-z0-9_]+$") then return nil, "Invalid scene name" end
    if type(xml) ~= "string" or xml == "" then return nil, "Empty scene XML" end
    local filename = name .. ".xml"
    if not file.Write(ready.data_path .. "/" .. filename, xml) then return nil, "Could not write scene XML" end
    return ready.absolute_directory .. "/" .. filename
end

return R
