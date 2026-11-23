-- data-final-fixes.lua — disable vanilla recipes/techs (after all base mod changes)

local seed = require("seed_loader")

log("[randputF] data-final-fixes.lua start")

-- Vanilla recipes that MUST stay enabled (rocket launch chain)
local rocket_recipe = (seed.meta and seed.meta.rocket and seed.meta.rocket.rocket_recipe) or "rocket-part"
local EXEMPT_RECIPES = {
  [rocket_recipe] = true,
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

-- Resources are placed per-planet in Factorio 2.0+. Force vanilla resources to
-- size=0 (they stay listed so default_enable_all doesn't re-enable them) and
-- register the randputF controls/entities with default frequency/size.
local patches = (seed.map or {}).patches or {}

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

local rock_coal_replaced = 0
local rock_coal_entities = {}
for entity_name, entity in pairs(data.raw["simple-entity"] or {}) do
  local minable = entity.minable
  if minable then
    local changed = false
    if minable.result == "coal" then
      minable.result = "stone"
      changed = true
    end
    for _, product in ipairs(minable.results or {}) do
      if (product.type == nil or product.type == "item") and product.name == "coal" then
        product.name = "stone"
        changed = true
      end
    end
    if changed then
      rock_coal_replaced = rock_coal_replaced + 1
      table.insert(rock_coal_entities, entity_name)
    end
  end
end
if rock_coal_replaced > 0 then
  log("[randputF] rocks: coal -> stone (" .. rock_coal_replaced .. ": " .. table.concat(rock_coal_entities, ", ") .. ")")
end

log("[randputF] data-final-fixes.lua done")
