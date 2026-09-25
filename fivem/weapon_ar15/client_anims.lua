-- weapon_ar15: custom third-person animations (anim@weapon_ar15, made in blender/ar15_anims.py).
--
--   low ready  upper-body loop 'hold' while the rifle is out and not aimed or fired
--   reload     when the game starts its own reload (R, ox_inventory, codem-inventory, empty
--              magazine...), the upper body plays 'reload' / 'reload_empty' on top of it; the
--              game's reload keeps running underneath, so ammo is handled exactly as before
--   magazine   during the reload the rifle's own magazine is hidden (locally) and a magazine prop
--              is drawn in the rifle / in the left hand, frame by frame from anim_data.lua; the
--              pulled one falls to the ground
--   parts      bolt, trigger, dust cover and bolt catch play the w_* clips on the rifle
--
-- The ped animations run on your own ped only and the game syncs them to the other players; the
-- magazine props and the rifle's parts are drawn locally, for every player nearby.

local A = AR15_ANIM
local DICT = A.dict
local WEAPON = `WEAPON_AR15`
local MAG_COMPONENT_MODEL = `w_ar_ar15_mag1`
local MAG_PROP_MODEL = `w_ar_ar15_mag_prop`
local PH_R_HAND, SKEL_L_HAND = 28422, 18905     -- the rifle hangs on PH_R_Hand
local HOLD_FLAGS = 1 + 16 + 32          -- loop, upper body only, player keeps control
local RELOAD_FLAGS = 16 + 32
local RELOADS = { A.reload, A.reload_empty }
local ROT_ORDER = 2                     -- Euler order passed to AttachEntityToEntity (ROT_ZXY)
local IsPedSwitchingWeapon = IsPedSwitchingWeapon or function() return false end   -- undocumented native

local function loaded()
    if HasAnimDictLoaded(DICT) then return true end
    RequestAnimDict(DICT)
    return false
end

local function propModelLoaded()
    if HasModelLoaded(MAG_PROP_MODEL) then return true end
    RequestModel(MAG_PROP_MODEL)
    return false
end

-- ------------------------------------------------------------------------------------------------
-- rotations: the magazine track stores quaternions, AttachEntityToEntity wants Euler angles
-- ------------------------------------------------------------------------------------------------
local AXES = { x = 1, y = 2, z = 3 }
local ORDERS = { 'zxy', 'zyx', 'xyz', 'xzy', 'yxz', 'yzx' }
-- M = R_i(a) * R_j(b) * R_k(c) for the order 'ijk'. The game's order 2 is 'zxy' (yaw, then pitch,
-- then roll); calibrate() checks it once against the game.
local eulerOrder = 'zxy'

local function quatMatrix(x, y, z, w)
    return {
        { 1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y) },
        { 2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x) },
        { 2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y) },
    }
end

local function axisMatrix(axis, deg)
    local r = math.rad(deg)
    local c, s = math.cos(r), math.sin(r)
    if axis == 1 then return { { 1, 0, 0 }, { 0, c, -s }, { 0, s, c } } end
    if axis == 2 then return { { c, 0, s }, { 0, 1, 0 }, { -s, 0, c } } end
    return { { c, -s, 0 }, { s, c, 0 }, { 0, 0, 1 } }
end

local function mul(a, b)
    local m = {}
    for i = 1, 3 do
        m[i] = {}
        for j = 1, 3 do
            m[i][j] = a[i][1] * b[1][j] + a[i][2] * b[2][j] + a[i][3] * b[3][j]
        end
    end
    return m
end

local function orderAxes(order)
    return AXES[order:sub(1, 1)], AXES[order:sub(2, 2)], AXES[order:sub(3, 3)]
end

-- rotation matrix of Euler angles {x, y, z} (degrees) in the given order
local function eulerMatrix(e, order)
    local i, j, k = orderAxes(order)
    return mul(mul(axisMatrix(i, e[i]), axisMatrix(j, e[j])), axisMatrix(k, e[k]))
end

-- Euler angles {x, y, z} (degrees) of a rotation matrix, for M = R_i(a) R_j(b) R_k(c)
local function matrixEuler(m, order)
    local i, j, k = orderAxes(order)
    local even = (order == 'xyz' or order == 'yzx' or order == 'zxy')
    local s = even and 1 or -1
    local sb = math.max(-1.0, math.min(1.0, s * m[i][k]))
    local e = {}
    e[j] = math.deg(math.asin(sb))
    e[i] = math.deg(math.atan(-s * m[j][k], m[k][k]))
    e[k] = math.deg(math.atan(-s * m[i][j], m[i][i]))
    return e
end

local function quatEuler(x, y, z, w)
    local e = matrixEuler(quatMatrix(x, y, z, w), eulerOrder)
    return e[1], e[2], e[3]
end

local function attach(obj, target, bone, px, py, pz, rx, ry, rz)
    AttachEntityToEntity(obj, target, bone, px, py, pz, rx, ry, rz, false, false, false, false, ROT_ORDER, true)
end

-- Attach a test object to a still one with known angles and read back how the game turned it.
local function calibrate()
    local t0 = GetGameTimer()
    while not propModelLoaded() do
        if GetGameTimer() - t0 > 10000 then return end
        Wait(50)
    end
    local p = GetEntityCoords(PlayerPedId()) + vector3(0.0, 0.0, 30.0)
    local base = CreateObject(MAG_PROP_MODEL, p.x, p.y, p.z, false, false, false)
    local test = CreateObject(MAG_PROP_MODEL, p.x, p.y, p.z, false, false, false)
    if base == 0 or test == 0 then
        if base ~= 0 then DeleteEntity(base) end
        if test ~= 0 then DeleteEntity(test) end
        return
    end
    for _, o in ipairs({ base, test }) do
        SetEntityVisible(o, false, false)
        SetEntityCollision(o, false, false)
    end
    FreezeEntityPosition(base, true)
    SetEntityRotation(base, 0.0, 0.0, 0.0, 2, true)
    local e = { 40.0, 25.0, 60.0 }          -- far enough apart that every order gives another result
    attach(test, base, 0, 0.0, 0.0, 0.0, e[1], e[2], e[3])
    for _ = 1, 5 do Wait(0) end
    local function axes(o)
        local c = GetEntityCoords(o)
        local x = GetOffsetFromEntityInWorldCoords(o, 1.0, 0.0, 0.0) - c
        local y = GetOffsetFromEntityInWorldCoords(o, 0.0, 1.0, 0.0) - c
        local z = GetOffsetFromEntityInWorldCoords(o, 0.0, 0.0, 1.0) - c
        return { { x.x, y.x, z.x }, { x.y, y.y, z.y }, { x.z, y.z, z.z } }
    end
    local b, t = axes(base), axes(test)
    DeleteEntity(test)
    DeleteEntity(base)
    -- relative rotation base^T * test (base should be the identity already)
    local bt = { { b[1][1], b[2][1], b[3][1] }, { b[1][2], b[2][2], b[3][2] }, { b[1][3], b[2][3], b[3][3] } }
    local rel = mul(bt, t)
    local best, bestErr = nil, math.huge
    for _, order in ipairs(ORDERS) do
        local m = eulerMatrix(e, order)
        local err = 0.0
        for i = 1, 3 do
            for j = 1, 3 do err = err + (m[i][j] - rel[i][j]) ^ 2 end
        end
        if err < bestErr then best, bestErr = order, err end
    end
    if best and bestErr < 0.01 then
        eulerOrder = best
    end
end

-- ------------------------------------------------------------------------------------------------
-- magazine track (anim_data.lua)
-- ------------------------------------------------------------------------------------------------
-- hand ('R' / 'L') and the attach offset (position, Euler angles) at clip frame f, nil = not shown
local function magPose(data, f)
    local i = math.floor(f)
    if i < 0 then i = 0 elseif i > data.frames then i = data.frames end
    local m0 = data.mag[i]
    if not m0 then return nil end
    local px, py, pz, qx, qy, qz, qw = m0[2], m0[3], m0[4], m0[5], m0[6], m0[7], m0[8]
    local m1 = data.mag[math.min(i + 1, data.frames)]
    local t = f - i
    if m1 and m1[1] == m0[1] and t > 0.0 then
        px, py, pz = px + (m1[2] - px) * t, py + (m1[3] - py) * t, pz + (m1[4] - pz) * t
        local s = (qx * m1[5] + qy * m1[6] + qz * m1[7] + qw * m1[8]) < 0.0 and -1.0 or 1.0
        qx, qy = qx + (s * m1[5] - qx) * t, qy + (s * m1[6] - qy) * t
        qz, qw = qz + (s * m1[7] - qz) * t, qw + (s * m1[8] - qw) * t
        local n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
        qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    end
    local rx, ry, rz = quatEuler(qx, qy, qz, qw)
    return m0[1], px, py, pz, rx, ry, rz
end

local function newProp(ped)
    if not propModelLoaded() then return nil end
    local p = GetEntityCoords(ped)
    local obj = CreateObject(MAG_PROP_MODEL, p.x, p.y, p.z + 0.5, false, false, false)
    if obj == 0 then return nil end
    SetEntityCollision(obj, false, false)
    return obj
end

local function deleteProp(obj)
    if obj and DoesEntityExist(obj) then
        DetachEntity(obj, false, false)
        DeleteEntity(obj)
    end
end

-- the rifle's own magazine (component object, model w_ar_ar15_mag1) of this ped
local function findMagComponent(ped)
    local weapon = GetCurrentPedWeaponEntityIndex(ped)
    if not weapon or weapon == 0 or not DoesEntityExist(weapon) then return nil end
    local wpos = GetEntityCoords(weapon)
    local best, bestD = nil, 0.6
    for _, obj in ipairs(GetGamePool('CObject')) do
        if GetEntityModel(obj) == MAG_COMPONENT_MODEL then
            if GetEntityAttachedTo(obj) == weapon then return obj end
            local d = #(GetEntityCoords(obj) - wpos)
            if d < bestD then best, bestD = obj, d end
        end
    end
    return best
end

local function playWeaponClip(ped, clip, stay)
    if not Config.WeaponPartAnims or not HasAnimDictLoaded(DICT) then return end
    local weapon = GetCurrentPedWeaponEntityIndex(ped)
    if weapon and weapon ~= 0 and DoesEntityExist(weapon) then
        PlayEntityAnim(weapon, clip, DICT, 1000.0, false, stay, false, 0.0, 0)
    end
end

-- dropped magazines ------------------------------------------------------------------------------
local dropped = {}

local function dropMagazine(ped, st, data)
    local prop = st.prop
    st.prop = nil
    if not prop then
        -- the rifle's magazine could not be hidden (it moves with the w_reload clip): drop a copy
        -- from the left hand
        prop = newProp(ped)
        if not prop then return end
        local _, x, y, z = magPose(data, data.drop)
        local p = GetPedBoneCoords(ped, SKEL_L_HAND, x or 0.0, y or 0.0, z or 0.0)
        SetEntityCoordsNoOffset(prop, p.x, p.y, p.z, false, false, false)
        SetEntityRotation(prop, 0.0, 0.0, GetEntityHeading(ped), 2, true)
    else
        DetachEntity(prop, true, true)
    end
    SetEntityCollision(prop, true, true)
    SetEntityDynamic(prop, true)
    ActivatePhysics(prop)
    local v = data.drop_velocity
    local w = GetOffsetFromEntityInWorldCoords(ped, v[1], v[2], v[3]) - GetEntityCoords(ped)
    local pv = GetEntityVelocity(ped)
    SetEntityVelocity(prop, pv.x + w.x, pv.y + w.y, pv.z + w.z)
    dropped[#dropped + 1] = { obj = prop, t = GetGameTimer(), pos = GetEntityCoords(prop) }
    while #dropped > Config.MaxDroppedMagazines do
        deleteProp(table.remove(dropped, 1).obj)
    end
end

local function updateDropped()
    local now = GetGameTimer()
    for i = #dropped, 1, -1 do
        local d = dropped[i]
        if not DoesEntityExist(d.obj) or now - d.t > Config.MagazineLifetime * 1000 then
            deleteProp(d.obj)
            table.remove(dropped, i)
        elseif d.pos and now - d.t > 400 then
            -- no physics on this object (it hangs where it was let go): put it on the ground
            if #(GetEntityCoords(d.obj) - d.pos) < 0.001 then
                PlaceObjectOnGroundProperly(d.obj)
            end
            d.pos = nil
        end
    end
end

-- ------------------------------------------------------------------------------------------------
-- per-ped drawing (every player nearby, you included)
-- ------------------------------------------------------------------------------------------------
local peds = {}
local frameNo = 0

local function endMag(ped, st)
    deleteProp(st.prop)
    st.prop, st.data, st.hide = nil, nil, nil
    if DoesEntityExist(ped) then SetPedCanArmIk(ped, true) end
end

local function startMag(ped, st, data)
    if st.data then endMag(ped, st) end
    st.data, st.dropped, st.lastF = data, false, 0.0
    -- hide the rifle's magazine only when the prop can take its place
    st.props = propModelLoaded()
    st.hide = st.props and findMagComponent(ped) or nil
    st.props = st.hide ~= nil
    playWeaponClip(ped, data.weapon_clip, false)
end

local function hideMag(ped, st)
    if not st.hide then return end
    if DoesEntityExist(st.hide) then
        SetEntityLocallyInvisible(st.hide)
    else
        st.hide = findMagComponent(ped)        -- the component was re-created
    end
end

local function updateMag(ped, st, data, f)
    if f < st.lastF - 5.0 then                -- the clip started over
        st.dropped = false
    end
    st.lastF = f
    hideMag(ped, st)
    SetPedCanArmIk(ped, false)                -- the left hand leaves the rifle: no grip IK
    if not st.dropped and f >= data.drop + 1.0 then       -- the track has no magazine from here
        st.dropped = true
        if Config.DropMagazines then
            dropMagazine(ped, st, data)
        else
            deleteProp(st.prop)
            st.prop = nil
        end
    end
    if not st.props then return end
    local hand, x, y, z, rx, ry, rz = magPose(data, f)
    if not hand then
        deleteProp(st.prop)
        st.prop = nil
        return
    end
    if not st.prop then
        st.prop = newProp(ped)
        if not st.prop then return end
    end
    attach(st.prop, ped, GetPedBoneIndex(ped, hand == 'R' and PH_R_HAND or SKEL_L_HAND), x, y, z, rx, ry, rz)
end

local function drawPed(ped, isMe)
    local st = peds[ped]
    if not st then
        st = {}
        peds[ped] = st
    end
    st.seen = frameNo
    -- shots: bolt and trigger
    local shooting = IsPedShooting(ped)
    if shooting and not st.shooting then
        local last = false
        if isMe then
            local ok, n = GetAmmoInClip(ped, WEAPON)
            last = ok and n == 0
        end
        playWeaponClip(ped, last and A.fire_last.clip or A.fire.clip, last)
    end
    st.shooting = shooting
    -- reload
    local data
    for _, d in ipairs(RELOADS) do
        if IsEntityPlayingAnim(ped, DICT, d.clip, 3) then
            data = d
            break
        end
    end
    if data then
        if st.data ~= data then startMag(ped, st, data) end
        st.until_ = nil
        updateMag(ped, st, data, GetEntityAnimCurrentTime(ped, DICT, data.clip) * data.frames)
    elseif st.data then
        -- our clip is over: the magazine stays drawn in the rifle while the game's reload finishes
        st.until_ = st.until_ or (GetGameTimer() + 1500)
        if IsPedReloading(ped) and GetGameTimer() < st.until_ then
            hideMag(ped, st)
        else
            endMag(ped, st)
            st.until_ = nil
        end
    end
end

CreateThread(function()
    loaded()
    propModelLoaded()
    calibrate()
end)

CreateThread(function()
    while true do
        frameNo = frameNo + 1
        local me = PlayerPedId()
        local myPos = GetEntityCoords(me)
        local busy = false
        for _, player in ipairs(GetActivePlayers()) do
            local ped = GetPlayerPed(player)
            if ped ~= 0 and DoesEntityExist(ped) and GetSelectedPedWeapon(ped) == WEAPON
                and #(GetEntityCoords(ped) - myPos) < Config.DrawDistance then
                busy = true
                drawPed(ped, ped == me)
            end
        end
        for ped, st in pairs(peds) do
            if st.seen ~= frameNo then
                if st.data then endMag(ped, st) end
                peds[ped] = nil
            end
        end
        updateDropped()
        Wait(busy and 0 or 250)
    end
end)

-- ------------------------------------------------------------------------------------------------
-- your own ped: low ready and the reload
-- ------------------------------------------------------------------------------------------------
local lowReady = GetResourceKvpInt('ar15_lowready_off') ~= 1
local reload = nil          -- { data = clip data, t = start time }
local reloadSeen = false    -- the game's current reload already got our animation
local lastClip = -1
local equippedAt = 0
local holdTried = 0
local aimReleasedAt = 0

RegisterCommand('ar15lowready', function()
    lowReady = not lowReady
    SetResourceKvpInt('ar15_lowready_off', lowReady and 0 or 1)
    local ped = PlayerPedId()
    if not lowReady and IsEntityPlayingAnim(ped, DICT, A.hold.clip, 3) then
        StopAnimTask(ped, DICT, A.hold.clip, 3.0)
    end
end, false)

local function aiming(ped)
    return IsPlayerFreeAiming(PlayerId()) or IsControlPressed(0, 25) or IsDisabledControlPressed(0, 25)
        or IsControlPressed(0, 24) or IsDisabledControlPressed(0, 24) or IsPedShooting(ped)
end

-- situations where the game's own upper-body animations must stay
local function overlayAllowed(ped)
    return GetFollowPedCamViewMode() ~= 4
        and not IsPedInAnyVehicle(ped, true) and not IsPedGettingIntoAVehicle(ped)
        and not IsPedInCover(ped, false) and not IsPedRagdoll(ped) and not IsPedFalling(ped)
        and not IsPedJumping(ped) and not IsPedClimbing(ped) and not IsPedVaulting(ped)
        and not IsPedSwimming(ped) and not IsPedDeadOrDying(ped, true)
        and not IsPedInParachuteFreeFall(ped) and GetPedParachuteState(ped) <= 0
        and not IsPedUsingAnyScenario(ped)
        and not IsPedSwitchingWeapon(ped) and not IsPedInMeleeCombat(ped)
        and not IsPedPerformingMeleeAction(ped) and not IsPedGoingIntoCover(ped)
end

local function ours(ped)
    if IsEntityPlayingAnim(ped, DICT, A.hold.clip, 3) then return true end
    for _, d in ipairs(RELOADS) do
        if IsEntityPlayingAnim(ped, DICT, d.clip, 3) then return true end
    end
    return false
end

-- another script (emote, inventory holster animation...) is playing an animation on the ped
local function otherAnim(ped)
    return GetScriptTaskStatus(ped, `SCRIPT_TASK_PLAY_ANIM`) ~= 7 and not ours(ped)
end

local function stopOurs(ped, speed)
    if IsEntityPlayingAnim(ped, DICT, A.hold.clip, 3) then StopAnimTask(ped, DICT, A.hold.clip, speed) end
    for _, d in ipairs(RELOADS) do
        if IsEntityPlayingAnim(ped, DICT, d.clip, 3) then StopAnimTask(ped, DICT, d.clip, speed) end
    end
end

local function startHold(ped, blend)
    if GetGameTimer() - holdTried < 300 then return end
    holdTried = GetGameTimer()
    TaskPlayAnim(ped, DICT, A.hold.clip, blend, 3.0, -1, HOLD_FLAGS, 0.0, false, false, false)
end

local function tickReload(ped)
    local data = reload.data
    if not IsEntityPlayingAnim(ped, DICT, data.clip, 3) then
        if GetGameTimer() - reload.t > 400 then reload = nil end     -- over (or taken over)
        return
    end
    if not overlayAllowed(ped) then
        StopAnimTask(ped, DICT, data.clip, 4.0)
        reload = nil
        return
    end
    local f = GetEntityAnimCurrentTime(ped, DICT, data.clip) * data.frames
    if f < data.release then
        -- the left hand is not back on the rifle yet
        DisablePlayerFiring(PlayerId(), true)
        DisableControlAction(0, 24, true)
        DisableControlAction(0, 257, true)
    elseif aiming(ped) then
        StopAnimTask(ped, DICT, data.clip, 8.0)
        reload = nil
    elseif f >= data.frames - 3 and Config.LowReady and lowReady and not IsPedSprinting(ped) then
        -- the clip ends in the low ready: go straight on into the loop
        holdTried = 0
        startHold(ped, 4.0)
        reload = nil
    end
end

local function tick(ped)
    local reloading = IsPedReloading(ped)
    if not reloading then
        reloadSeen = false
        if not reload then
            local ok, n = GetAmmoInClip(ped, WEAPON)
            if ok then lastClip = n end
        end
    end
    local allowed = overlayAllowed(ped)

    if reload then
        tickReload(ped)
        return
    end

    if Config.CustomReload and reloading and not reloadSeen and allowed and not otherAnim(ped) and loaded() then
        local data = lastClip == 0 and A.reload_empty or A.reload
        TaskPlayAnim(ped, DICT, data.clip, 6.0, 3.0, -1, RELOAD_FLAGS, 0.0, false, false, false)
        reload = { data = data, t = GetGameTimer() }
        reloadSeen = true
        return
    end

    local playingHold = IsEntityPlayingAnim(ped, DICT, A.hold.clip, 3)
    local aim = aiming(ped)
    if aim then aimReleasedAt = GetGameTimer() end
    local want = Config.LowReady and lowReady and allowed and not reloading and not aim
        and (Config.LowReadyWhileSprinting or not IsPedSprinting(ped))
        and GetGameTimer() - equippedAt > 1500 and GetGameTimer() - aimReleasedAt > 150
    if want then
        if not playingHold and not otherAnim(ped) and loaded() then startHold(ped, 3.0) end
    elseif playingHold then
        StopAnimTask(ped, DICT, A.hold.clip, aim and 8.0 or 3.0)
    end
end

CreateThread(function()
    local armed = false
    while true do
        local ped = PlayerPedId()
        if GetSelectedPedWeapon(ped) == WEAPON and not IsEntityDead(ped) then
            if not armed then
                armed = true
                equippedAt = GetGameTimer()
                lastClip = -1
            end
            tick(ped)
            Wait(0)
        else
            if armed then
                armed = false
                reload = nil
                stopOurs(ped, 4.0)
                SetPedCanArmIk(ped, true)
            end
            Wait(250)
        end
    end
end)

AddEventHandler('onResourceStop', function(name)
    if name ~= GetCurrentResourceName() then return end
    local ped = PlayerPedId()
    stopOurs(ped, 8.0)
    SetPedCanArmIk(ped, true)
    for p, st in pairs(peds) do
        deleteProp(st.prop)
        if DoesEntityExist(p) then SetPedCanArmIk(p, true) end
    end
    for _, d in ipairs(dropped) do deleteProp(d.obj) end
end)
