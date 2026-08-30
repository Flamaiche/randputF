-- data-final-fixes.lua — disable vanilla recipes/techs (after all base mod changes)

local seed = {}
do
  local ok, loaded = pcall(require, "seed.seed")
  if ok and type(loaded) == "table" then
    seed = loaded
  end
end

log("[randputF] data-final-fixes.lua start")

-- Vanilla recipes that MUST stay enabled (rocket launch chain)
local EXEMPT_RECIPES = {
  ["rocket-part"] = true,
}

-- Vanilla technologies that MUST stay enabled
local EXEMPT_TECHS = {}

local recipe_disabled = 0
local tech_disabled = 0

-- Disable ALL vanilla recipes except exempt ones and randputF recipes
for recipe_name, recipe_data in pairs(data.raw.recipe or {}) do
  if not EXEMPT_RECIPES[recipe_name] and not recipe_name:find("^randputf%-") then
    local ok, err = pcall(function()
      recipe_data.enabled = false
      recipe_data.hidden = true
    end)
    if ok then
      recipe_disabled = recipe_disabled + 1
    else
      log("[randputF] FAIL disable recipe '" .. recipe_name .. "': " .. tostring(err))
    end
  end
end

-- Disable ALL vanilla technologies except exempt ones and randputF techs
for tech_name, tech_data in pairs(data.raw.technology or {}) do
  if not EXEMPT_TECHS[tech_name] and not tech_name:find("^randputf%-") then
    local ok, err = pcall(function()
      tech_data.enabled = false
      tech_data.hidden = true
    end)
    if ok then
      tech_disabled = tech_disabled + 1
    else
      log("[randputF] FAIL disable tech '" .. tech_name .. "': " .. tostring(err))
    end
  end
end

log("[randputF] disabled: " .. recipe_disabled .. " recipes, " .. tech_disabled .. " techs")

-- Hide vanilla resource autoplace controls from the map-gen GUI (their
-- resources list) so only randputF patches are visible there.
for control_name, control in pairs(data.raw["autoplace-control"] or {}) do
  if not control_name:find("^randputf%-") and control.category == "resource" then
    control.hidden = true
  end
end

-- Resources are placed per-planet in Factorio 2.0. Force vanilla resources to
-- size=0 (they stay listed so default_enable_all doesn't re-enable them) and
-- register the randputF controls/entities with default frequency/size.
local seed_ok, seed_data = pcall(require, "seed.seed")
local patches = {}
if seed_ok and type(seed_data) == "table" then
  patches = (seed_data.map or {}).patches or {}
end

for planet_name, planet in pairs(data.raw["planet"] or {}) do
  local mgs = (planet.map_gen_settings or {})
  local entity_settings = (((mgs.autoplace_settings or {}).entity or {}).settings) or {}
  local controls = (mgs.autoplace_controls or {})

  -- Vanilla resource controls -> size 0 (never placed), remains listed
  for resource_name, resource_data in pairs(data.raw["resource"] or {}) do
    if not resource_name:find("^randputf%-") then
      controls[resource_name] = { frequency = 1, size = 0, richness = 1 }
    end
  end

  -- Register randputF resources from the seed
  local seen = {}
  local i = 0
  for _, patch in ipairs(patches) do
    local prefix = patch.kind == "fluid" and "randputf-oil-" or "randputf-minerai-"
    local entity_name = prefix .. patch.resource
    if not seen[entity_name] then
      seen[entity_name] = true
      i = i + 1
      controls["randputf-ctl-" .. i] = { frequency = 1, size = 1, richness = 1 }
      entity_settings[entity_name] = { frequency = 1, size = 1, richness = 1 }
    end
  end
end
log("[randputF] planet autoplace updated")

log("[randputF] data-final-fixes.lua done")
