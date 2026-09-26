-- weapon_styles (server): checks a player's choice and puts it in their player state bag, which
-- OneSync sends to every client (they apply it to that player's ped).

local valid = {}
for _, cat in ipairs(Catalog.categories) do
    valid[cat.key] = { default = true }
    for _, st in ipairs(cat.styles) do valid[cat.key][st.id] = true end
end

local INTERVAL = 150        -- ms between two state bag updates of one player
local last, pending = {}, {}

local function apply(src, prefs)
    last[src] = GetGameTimer()
    local clean = {}
    for key, ids in pairs(valid) do
        local id = prefs[key]
        clean[key] = (type(id) == 'string' and ids[id]) and id or (Config.Defaults[key] or 'default')
    end
    Player(src).state:set('wstyles', clean, true)
end

RegisterNetEvent('weapon_styles:set', function(prefs)
    local src = source
    if type(prefs) ~= 'table' then return end
    local wait = last[src] and last[src] + INTERVAL - GetGameTimer() or 0
    if wait <= 0 then
        apply(src, prefs)
        return
    end
    -- clicking through the menu: the latest choice goes out when the interval is over
    local queued = pending[src] ~= nil
    pending[src] = prefs
    if queued then return end
    SetTimeout(wait, function()
        local p = pending[src]
        pending[src] = nil
        if p and GetPlayerName(src) then apply(src, p) end
    end)
end)

AddEventHandler('playerDropped', function()
    last[source] = nil
    pending[source] = nil
end)
