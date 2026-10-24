-- Adaptateur autonome vers l'état géodésique public de BeamNG.earth.
-- Ne touche pas aux fichiers du mod BeamNG.earth.
local bridge = require('bngGpsBridge/gpsbridge')
local M = {}

function M.onUpdate(dtReal)
  local earth = rawget(_G, 'beamngEarth_core')
  if not earth or type(earth._state) ~= 'function' then return end
  local ok, state = pcall(earth._state)
  if not ok or type(state) ~= 'table' then return end
  bridge.update(dtReal, state.player, state.anchor)
end

function M.onExtensionUnloaded()
  bridge.close()
end

return M
