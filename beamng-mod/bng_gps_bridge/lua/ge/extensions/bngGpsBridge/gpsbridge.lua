-- Optional localhost GPS relay. Only exports the geodetic pose already computed by BeamNG.earth.
-- Nonblocking and bounded: it never waits for Windows or accumulates an unbounded send queue.
local M = {}
local socket = require('socket')
local cfgOk, cfg = pcall(require, 'bngGpsBridge/config')
if not cfgOk then cfg = { enabled = false, host = '127.0.0.1', port = 47720, interval = 1 / 30 } end
local sock, connecting, elapsed, seq, streamId, lastHeading = nil, false, 0, 0, nil, nil
local queue, queuedBytes = {}, 0
local loggedStart, loggedConnected, lastStatsAt, lastError, retryRemaining = false, false, 0, nil, 0
local lastTimestampMs = os.time() * 1000

local function nextTimestampMs(interval)
  -- os.time() has only whole-second precision. Preserve UTC epoch milliseconds while
  -- advancing monotonically at the stream cadence so Android/Maps don't see 30 fixes
  -- with an identical timestamp each second.
  lastTimestampMs = math.max(os.time() * 1000, lastTimestampMs + interval * 1000)
  lastTimestampMs = math.floor(lastTimestampMs)
  return lastTimestampMs
end

local function status(message)
  if log then log('I', 'beamngEarth.gpsbridge', message) end
end

local function close()
  if sock then pcall(function() sock:close() end) end
  if loggedConnected then status('liaison TCP locale perdue; nouvelle tentative automatique') end
  loggedConnected = false
  sock, connecting, queue, queuedBytes = nil, false, {}, 0
end

local function connect()
  if sock or not cfg.enabled or retryRemaining > 0 then return end
  local candidate = socket.tcp()
  sock = candidate
  candidate:settimeout(0)
  local ok, err = candidate:connect(cfg.host or '127.0.0.1', cfg.port or 47720)
  connecting = not ok and (err == 'timeout' or err == 'Operation already in progress')
  if not ok and not connecting then
    lastError = tostring(err)
    if log then log('W', 'beamngEarth.gpsbridge', 'connexion TCP impossible: ' .. lastError) end
    retryRemaining = 2
    close()
  end
end

local function ready()
  if not sock then return false end
  if connecting then
    local _, writable = socket.select(nil, { sock }, 0)
    if not writable or #writable == 0 then return false end
    -- LuaSocket returns (peerAddress, peerPort) on success, so testing the
    -- second result as an error mistakes the valid peer port (47720) for failure.
    local peerAddress, err = sock:getpeername()
    if not peerAddress then
      lastError = tostring(err)
      if log then log('W', 'beamngEarth.gpsbridge', 'connexion TCP échouée: ' .. lastError) end
      retryRemaining = 2
      close(); return false
    end
    connecting = false
  end
  if not loggedConnected then status('connecté au connecteur Windows sur 127.0.0.1:' .. tostring(cfg.port or 47720)); loggedConnected = true end
  return true
end

local function sendQueued()
  if not ready() then return end
  local msg = queue[1]
  if not msg then return end
  local sent, err, last = sock:send(msg)
  local count = sent or last or 0
  if count > 0 then
    if count >= #msg then queuedBytes = queuedBytes - #msg; table.remove(queue, 1)
    else queue[1] = msg:sub(count + 1); queuedBytes = queuedBytes - count end
  elseif err ~= 'timeout' then
    lastError = tostring(err)
    if log then log('W', 'beamngEarth.gpsbridge', 'envoi TCP échoué: ' .. lastError) end
    retryRemaining = 2
    close()
  end
end

local function update(dt, p, anchor)
  if not cfg.enabled then close(); return end
  if not loggedStart then
    status('pont activé; attente d’un véhicule et d’une ancre géographique Earth')
    loggedStart = true
  end
  if not p or p.camera or type(p.lat) ~= 'number' or type(p.lon) ~= 'number' then return end
  retryRemaining = math.max(0, retryRemaining - (dt or 0))
  elapsed = elapsed + (dt or 0)
  connect(); sendQueued()
  local interval = math.max(1 / 30, math.min(1, tonumber(cfg.interval) or 1 / 30))
  if elapsed < interval then return end
  elapsed = elapsed % interval
  local northX, northY = 0, 1
  if anchor and anchor.northAt then northX, northY = anchor:northAt(p.x or 0, p.y or 0) end
  local eastX, eastY = northY, -northX
  local vx, vy = p.vx or 0, p.vy or 0
  local velocityNorth = vx * northX + vy * northY
  local velocityEast = vx * eastX + vy * eastY
  local horizontal = math.sqrt(velocityEast^2 + velocityNorth^2)
  local heading = lastHeading
  if horizontal > 0.8 then
    heading = math.deg(math.atan2(velocityEast, velocityNorth)) % 360
    lastHeading = heading
  end
  if not streamId then streamId = tostring(os.time()) .. '-' .. tostring(math.random(100000, 999999)) end
  seq = seq + 1
  local altitude = type(p.alt) == 'number' and string.format('%.3f', p.alt) or 'null'
  local speed = tonumber(p.speed) or math.sqrt(vx^2 + vy^2 + (p.vz or 0)^2)
  local message = string.format('{"version":1,"type":"position","source":"beamng-earth","stream_id":"%s","seq":%d,"timestamp_utc_ms":%d,"latitude":%.10f,"longitude":%.10f,"altitude_m":%s,"speed_mps":%.4f,"heading_deg":%s,"test":false}\n',
    streamId, seq, nextTimestampMs(interval), p.lat, p.lon, altitude, speed,
    heading and string.format('%.2f', heading) or 'null')
  if #message <= 4096 then
    if queuedBytes + #message > 8192 then close() else queue[#queue + 1] = message; queuedBytes = queuedBytes + #message end
  end
  if os.time() - lastStatsAt >= 2 then
    lastStatsAt = os.time()
    status(string.format('positions préparées: %d; dernière position %.6f, %.6f%s', seq, p.lat, p.lon,
      loggedConnected and '; liaison TCP active' or '; en attente du connecteur'))
  end
end

function M.update(dt, p, anchor)
  local ok, err = pcall(update, dt, p, anchor)
  if not ok then
    local detail = tostring(err)
    if detail ~= lastError and log then log('E', 'beamngEarth.gpsbridge', 'pont GPS neutralis\195\169 apr\195\168s une erreur: ' .. detail) end
    lastError = detail
    retryRemaining = 2
    close()
  end
end

function M.close() close() end
return M
