-- data-updates.lua — resource entities: minerai, oil

local resource_autoplace = require("resource-autoplace")

local seed = {}
do
  local ok, loaded = pcall(require, "seed.seed")
  if ok and type(loaded) == "table" then
    seed = loaded
  end
end

log("[randputF] data-updates.lua start")

-- Ré-armement des véhicules selon la seed : clone de chaque arme par véhicule,
-- portée scalable selon la taille de l'entité. On ne garde que les armes tirées.
do
  local scaling = (seed.pools or {}).vehicle_range_scaling or {}
  local base_size = scaling.base_size or 2.0
  local range_scale = scaling.scale or 0.4

  local function entity_size(entity)
    if not entity or not entity.selection_box then return 0 end
    local box = entity.selection_box
    -- Extent complet (x2-x1, y2-y1) : cohérent avec les tailles mesurées
    -- (tank 2.6, spidertron 2, artillery-wagon 6).
    return math.max(math.abs((box[2] or box[1])[1] - box[1][1]), math.abs((box[2] or box[1])[2] - box[1][2]))
  end

  local function scaled_range(orig, size)
    local factor = 1 + math.max(size - base_size, 0) * range_scale
    return math.floor(orig * factor + 0.5)
  end

  local function clone_gun_for(vehicle, gun, size)
    local src = data.raw["gun"][gun]
    if not src then
      log("[randputF] arme de vehicule inconnue: " .. tostring(gun))
      return nil
    end
    local clone = table.deepcopy(src)
    local clone_name = "randputf-" .. vehicle .. "-" .. gun
    clone.name = clone_name
    if clone.attack_parameters and clone.attack_parameters.range then
      clone.attack_parameters.range = scaled_range(clone.attack_parameters.range, size)
    end
    data:extend{clone}
    return clone_name
  end

  local assigned = (seed.vehicle_armament) or {}
  for vehicle, guns in pairs(assigned) do
    local proto = data.raw["car"][vehicle]
      or data.raw["spider-vehicle"][vehicle]
      or data.raw["artillery-wagon"][vehicle]
    if not proto then
      log("[randputF] vehicule arme introuvable: " .. tostring(vehicle))
    else
      local size = entity_size(proto)
      local valid = {}
      for _, gun in ipairs(guns or {}) do
        local clone_name = clone_gun_for(vehicle, gun, size)
        if clone_name then valid[#valid + 1] = clone_name end
      end
      if #valid > 0 then
        if data.raw["car"][vehicle] or data.raw["spider-vehicle"][vehicle] then
          proto.guns = valid
        elseif data.raw["artillery-wagon"][vehicle] then
          proto.gun = valid[1]
        end
        log("[randputF] vehicule re-arme: " .. vehicle .. " <- [" .. table.concat(valid, ",") .. "]")
      end
    end
  end
end

local solid_template = nil
local fluid_template = nil
for name, entity in pairs(data.raw["resource"] or {}) do
  if entity.resource_category == "basic-solid" and not solid_template then
    solid_template = table.deepcopy(entity)
  elseif entity.resource_category == "basic-fluid" and not fluid_template then
    fluid_template = table.deepcopy(entity)
  end
  if solid_template and fluid_template then break end
end
if not solid_template then solid_template = table.deepcopy(data.raw["resource"]["iron-ore"] or {}) end
if not fluid_template then fluid_template = table.deepcopy(data.raw["resource"]["crude-oil"] or {}) end

local patches = (seed.map or {}).patches or {}

local function get_primary_icon(proto)
  if proto == nil then return nil end
  if proto.icon ~= nil then
    return proto.icon, proto.icon_size or 64
  end
  if proto.icons ~= nil and proto.icons[1] ~= nil then
    local icon = proto.icons[1]
    return icon.icon, icon.icon_size or proto.icon_size or 64
  end
  return nil
end

-- Types item-like : armes, capsules, modules etc. ont leur propre table data.raw.
local ITEM_LIKE_TYPES = {
  "item", "gun", "tool", "capsule", "ammo", "armor",
  "repair-tool", "mining-tool", "module", "item-with-entity-data",
  "selection-tool", "blueprint", "copy-paste-tool",
  "deconstruction-item", "upgrade-item", "rail-planner",
}

local function find_item_proto(name)
  if not name then return nil end
  if data.raw.item and data.raw.item[name] then return data.raw.item[name] end
  for _, t in ipairs(ITEM_LIKE_TYPES) do
    local table_proto = data.raw[t]
    if table_proto and table_proto[name] then
      return table_proto[name]
    end
  end
  return nil
end

local seen = {}
local unique_patches = {}
for _, patch in ipairs(patches) do
  local prefix = patch.kind == "fluid" and "randputf-oil-" or "randputf-minerai-"
  local entity_name = prefix .. patch.resource
  if not seen[entity_name] then
    seen[entity_name] = true
    table.insert(unique_patches, patch)
  end
end

log("[randputF] " .. #unique_patches .. " unique resource entities to create")

local autoplace_controls = {}
local resources = {}
local seed_value = (seed.meta and seed.meta.seed) or 1

-- Seeds >2^53 : on dérive une graine 32 bits déterministe (hash polynôme mod 2^31).
local function seed_hash(value)
  local h = 0
  local s = tostring(value)
  for j = 1, #s do
    h = (h * 131 + s:byte(j)) % 2147483647
  end
  return h
end
local map_seed_hash = seed_hash(seed_value)

for i, patch in ipairs(unique_patches) do
  local resource_name = patch.resource
  local is_fluid = patch.kind == "fluid"
  local prefix = is_fluid and "randputf-oil-" or "randputf-minerai-"
  local new_entity_name = prefix .. resource_name
  local control_name = "randputf-ctl-" .. i

  table.insert(autoplace_controls, {
    type = "autoplace-control",
    name = control_name,
    localised_name = {"", "[entity=" .. new_entity_name .. "] ", {"", (resource_name:gsub("-", " "))}},
    richness = true,
    category = "resource",
    order = "b-no-resource-regular",
  })

  resource_autoplace.initialize_patch_set(new_entity_name, true)

  local source = is_fluid and fluid_template or solid_template
  local new_entity = table.deepcopy(source)
  new_entity.name = new_entity_name
  -- Descriptif : préfixe [item=...]/[fluid=...] pour distinguer les fluides.
  local icon_tag = is_fluid and ("[fluid=" .. resource_name .. "] ")
    or ("[item=" .. resource_name .. "] ")
  new_entity.localised_name = {"", icon_tag, (resource_name:gsub("-", " "))}

  if is_fluid then
    new_entity.minable = {
      mining_time = 1,
      results = {{ type = "fluid", name = resource_name, amount = 1 }},
    }
    new_entity.resource_category = "basic-fluid"
    -- Puits fluides : posés explicitement au runtime, autoplace=0 requis (le moteur
    -- exige un spécification d'autoplace). Richesse fixée via entity.amount.
    new_entity.autoplace = resource_autoplace.resource_autoplace_settings{
      name = new_entity_name,
      patch_set_name = new_entity_name,
      autoplace_control_name = control_name,
      base_density = 0,
      base_spots_per_km2 = 2,
      has_starting_area_placement = true,
      seed1 = map_seed_hash * 1000 + i,
    }
  else
    new_entity.minable = {
      mining_time = 1,
      results = {{ type = "item", name = resource_name, amount = 1 }},
    }
    new_entity.resource_category = "basic-solid"

    new_entity.autoplace = resource_autoplace.resource_autoplace_settings{
      name = new_entity_name,
      patch_set_name = new_entity_name,
      autoplace_control_name = control_name,
      -- Items aussi posés au runtime : autoplace=0 requis, richesse via entity.amount.
      base_density = 0,
      base_spots_per_km2 = 2,
      has_starting_area_placement = true,
      seed1 = map_seed_hash * 1000 + i,
    }
  end
  new_entity.placeable_by = nil

  local icon_src = is_fluid and data.raw["fluid"][resource_name] or find_item_proto(resource_name)
  local icon_path, icon_size = get_primary_icon(icon_src)
  if icon_path then
    new_entity.icon = icon_path
    new_entity.icon_size = icon_size
  elseif not is_fluid then
    -- Patch item sans icône résolue → icône par défaut du template (iron-ore).
    log("[randputF] WARN icone introuvable pour patch item: " .. (resource_name or "?") ..
        " (proto_type=" .. tostring(icon_src and icon_src.type) .. ")")
  end
  if not is_fluid and icon_path then
    -- Minerais solides : icône item sur le sol (stages 4 positions).
    new_entity.stages = {
      sheets = {
        {variation_count = 1, filename = icon_path, size = icon_size, scale = 0.35, shift = {0.2, 0.6}},
        {variation_count = 1, filename = icon_path, size = icon_size, scale = 0.25, shift = {-0.5, 0.2}},
        {variation_count = 1, filename = icon_path, size = icon_size, scale = 0.45, shift = {0, 0}},
        {variation_count = 1, filename = icon_path, size = icon_size, scale = 0.4, shift = {-0.2, -0.6}},
      },
    }
    new_entity.stage_counts = {4}
    new_entity.stages_effect = nil
  end

  new_entity.map_color = {
    r = (math.floor((map_seed_hash * 131 + i * 47) % 101) + 30) / 255,
    g = (math.floor((map_seed_hash * 197 + i * 83) % 101) + 30) / 255,
    b = (math.floor((map_seed_hash * 251 + i * 127) % 101) + 30) / 255,
  }

  table.insert(resources, new_entity)
end

local ok, err = pcall(data.extend, data, autoplace_controls)
if ok then
  log("[randputF] created " .. #autoplace_controls .. " autoplace controls")
else
  log("[randputF] FAIL autoplace controls: " .. tostring(err))
end

ok, err = pcall(data.extend, data, resources)
if ok then
  log("[randputF] created " .. #resources .. " resource entities")
else
  log("[randputF] FAIL resource entities: " .. tostring(err))
end

log("[randputF] resources: " .. #resources .. " created")

-- Lacs de fluide : 3e type de ressource. Lacs dessinés par le moteur d'altitude
-- (tuile fantôme randputf-lac-neutre), remplis au runtime (control.lua).
-- Ici : prototype de tuile PAR fluide de la seed, autoplace=0.
local lake_list = (seed.map or {}).lakes or {}
if #lake_list > 0 then
-- Couleur de lac : teinte réelle du fluide, remontée en luminosité pour rester visible.
-- Gamme claire autorisée (vert/jaune/orange/bleu/cyan) — bruns et verts foncés exclus.
local lake_fallbacks = {
  ["crude-oil"]     = { 0.25, 0.55, 0.70 },  -- bleu turquoise clair (pas brun)
  ["steam"]         = { 0.55, 0.75, 0.95 },  -- bleu pâle
  ["hydrogen"]      = { 0.30, 0.80, 0.85 },  -- cyan vif
  ["nitric-acid"]   = { 1.00, 0.70, 0.40 },  -- orange clair
  ["sulfuric-acid"] = { 0.95, 0.85, 0.40 },  -- jaune clair
}
-- Palette pastel pour la minimap : luminosité ≥ 0.60, saturation ≥ 0.35,
-- plafond 0.90.  Les patches ressources utilisent des couleurs vives
-- (composantes 30..130 / 255) ; les lacs en clair se distinguent
-- naturellement sans les écraser.
local LAKE_MIN_LUM  = 0.60
local LAKE_MIN_SAT  = 0.35
local LAKE_MAX_LUM  = 0.90

local function clamp01(v) return math.max(0, math.min(1, v)) end

-- Les teintes claires « acceptables » (vert clair → orange → bleu/cyan).
-- Un triplet est accepté si sa teinte dominante tombe dans l'une de ces
-- fenêtres (hautes composantes, faible composante), ou s'il est pastel clair.
local function hue_allowed(r, g, b)
  local mx, mn = math.max(r, g, b), math.min(r, g, b)
  local d = mx - mn
  if d < 0.15 then
    -- Couleur quasi-grise mais CLAIRE : acceptable uniquement si lumineuse
    return r * 0.299 + g * 0.587 + b * 0.114 >= 0.68
  end
  local h
  if mx == r then
    h = ((g - b) / d) % 6
  elseif mx == g then
    h = (b - r) / d + 2
  else
    h = (r - g) / d + 4
  end
  h = h * 60  -- degrés (0..360)
  -- Fenêtres claires : jaune/orange (15..60), vert clair (~75..140),
  -- cyan/bleu clair (165..230). On EXCLUT le rouge vif, le brun, le vert
  -- foncé et le bleu nuit.
  return (h >= 12 and h <= 62)
      or (h >= 70 and h <= 150)
      or (h >= 165 and h <= 235)
end

-- Iterator : ajuste un triplet pour tomber dans la gamme claire autorisée.
-- On essaie d'abord de garder la teinte d'origine (si elle est claire), sinon
-- on la rabat vers la teinte claire la plus proche de la gamme.
local function force_lake_range(r, g, b)
  -- Éclaircissement : remonte la luminosité au minimum
  local lum = r * 0.299 + g * 0.587 + b * 0.114
  if lum < LAKE_MIN_LUM then
    local k = LAKE_MIN_LUM / math.max(lum, 0.001)
    r, g, b = clamp01(r * k), clamp01(g * k), clamp01(b * k)
  end
  -- Si la teinte est déjà dans la gamme claire, parfait.
  if hue_allowed(r, g, b) then return r, g, b end
  -- Sinon on rabat vers la teinte claire la plus proche de la gamme.
  -- On garde la dominante et on mappe sur une teinte claire voisine.
  local mx = math.max(r, g, b)
  local t = {
    { 0.30, 0.80, 0.85 },  -- cyan
    { 0.55, 0.75, 0.95 },  -- bleu pâle
    { 0.70, 0.85, 0.40 },  -- vert clair
    { 1.00, 0.70, 0.35 },  -- orange
    { 0.95, 0.85, 0.40 },  -- jaune
  }
  local best, best_d = t[1], math.huge
  for i = 1, #t do
    local c = t[i]
    local d = (c[1]-r)^2 + (c[2]-g)^2 + (c[3]-b)^2
    if d < best_d then best_d, best = d, c end
  end
  return best[1], best[2], best[3]
end

local function pastel_floor(r, g, b)
  -- 1) Force la gamme claire (teinte + luminosité)
  r, g, b = force_lake_range(r, g, b)

  -- 2) Saturation minimale (écart minimal entre la dominante et la moyenne)
  local mx = math.max(r, g, b)
  local mn = math.min(r, g, b)
  local spread = mx - mn
  if spread < LAKE_MIN_SAT then
    local boost = (LAKE_MIN_SAT - spread) / 2
    if mx == r then
      r = clamp01(r + boost); g = clamp01(g - boost * 0.4); b = clamp01(b - boost * 0.4)
    elseif mx == g then
      g = clamp01(g + boost); r = clamp01(r - boost * 0.4); b = clamp01(b - boost * 0.4)
    else
      b = clamp01(b + boost); r = clamp01(r - boost * 0.4); g = clamp01(g - boost * 0.4)
    end
    -- Re-vérifie la teinte après le boost (peut avoir dérivé)
    if not hue_allowed(r, g, b) then
      r, g, b = force_lake_range(r, g, b)
    end
  end

  -- 3) Plafond luminosité
  local lum = r * 0.299 + g * 0.587 + b * 0.114
  if lum > LAKE_MAX_LUM then
    local k = LAKE_MAX_LUM / math.max(lum, 0.001)
    r, g, b = clamp01(r * k), clamp01(g * k), clamp01(b * k)
  end

  return r, g, b
end

local function lake_color(fluid, base)
  local r, g, b = base[1] or 0, base[2] or 0, base[3] or 0

  -- Table de secours pour les fluides sans chromatisme propre (noir/blanc)
  -- ou dont la teinte sort de la gamme claire.
  local spread = math.max(r, g, b) - math.min(r, g, b)
  local lum = r * 0.299 + g * 0.587 + b * 0.114
  if lum < 0.18 or spread < 0.10 or not hue_allowed(r, g, b) then
    local fb = lake_fallbacks[fluid]
    if fb then r, g, b = fb[1], fb[2], fb[3] end
  end

  local pr, pg, pb = pastel_floor(r, g, b)
  return { pr, pg, pb }
end

-- 1) Lacs via le moteur d'altitude natif de Factorio. L'eau vanilla est
-- neutralisée (property_expression_names → -inf) et remplacée par la tuile
-- fantôme randputf-lac-neutre (même autoplace water_base). Au runtime
-- (control.lua) : flood-fill → randputf-lac-<fluide>.
local water_tiles = water_tile_type_names or {}
if #water_tiles == 0 then
  water_tiles = {
    "water", "deepwater", "water-shallow", "water-green",
    "deepwater-green", "water-mud", "water-wube",
  }
end
-- Water_tiles en lookup O(1) pour le patch des transitions berges.
local water_has = {}
for _, tname in ipairs(water_tiles) do
  water_has[tname] = true
end

-- Fluide fantôme : marqueur pour les tuiles-lac non encore remplies.
local PHANTOM_FLUID = "randputf-neutre"
local PHANTOM_TILE = "randputf-lac-neutre"
data:extend{
  {
    type = "fluid",
    name = PHANTOM_FLUID,
    subgroup = "fluid",
    default_temperature = 25,
    base_color = { 1, 1, 1 },
    flow_color = { 1, 1, 1 },
    icon = "__randputF__/graphics/ghost-fluid.png",
    icon_size = 64,
    order = "zzz[randputf-neutre]",
  },
}

-- Tuile fantôme : copie de l'eau avec le fluide fantôme et même autoplace (water_base).
local tile_water_proto = data.raw.tile.water or data.raw.tile.deepwater
if tile_water_proto then
  local phantom = table.deepcopy(tile_water_proto)
  phantom.name = PHANTOM_TILE
  phantom.localised_name = { "randputf.phantom-lake-name" }
  phantom.fluid = PHANTOM_FLUID
  phantom.order = "a-water-zz-0"
  phantom.autoplace = { probability_expression = "water_base(0, 100)" }
  -- Fantôme entièrement blanc : pas de shader water, tint + map_color = blanc.
  phantom.effect = nil
  phantom.effect_color = nil
  phantom.effect_color_secondary = nil
  phantom.map_color = { 255, 255, 255 }
  if phantom.variants and phantom.variants.main then
    for _, layer in ipairs(phantom.variants.main) do
      layer.tint = { 1, 1, 1, 1 }
    end
  end
  data:extend{phantom}
  log("[randputF] lacs: tuile fantome " .. PHANTOM_TILE .. " creee (moteur altitude water_base)")
end

-- Neutralisation tuiles eau vanilla : probability → -inf via property_expression_names.
-- Le fantôme prend leur place (même water_base).
data:extend{
  { type = "noise-expression", name = "randputf-no-water", expression = "-999" },
}
local purged = 0
do
  local nauvis = data.raw["planet"] and data.raw["planet"].nauvis
  if nauvis and nauvis.map_gen_settings then
    local pen = nauvis.map_gen_settings.property_expression_names or {}
    for _, tname in ipairs(water_tiles) do
      local t = data.raw.tile[tname]
      if t then
        pen["tile:" .. tname .. ":probability"] = "randputf-no-water"
        purged = purged + 1
      end
    end
    nauvis.map_gen_settings.property_expression_names = pen
  else
    log("[randputF] lacs: WARN planete nauvis introuvable — eau vanilla non neutralisée au mapgen")
  end
end
log("[randputF] lacs: eau vanilla neutralisée (" .. purged .. " tuiles) -> " .. PHANTOM_TILE)

  local tile_template = data.raw.tile.water or data.raw.tile.deepwater
  if tile_template then
    -- (A1) Marqueurs de berge en table Lua locale, jamais sur le prototype :
    -- `lake_borders[tile_name]` est lu directement par le patch des transitions
    -- plus bas (pas de clé custom portée par data.raw.tile).
    local lake_borders = {}
    local lake_ctl_map = {}
    local lake_ctls = {}
    local lake_tiles = {}
    for i, lake in ipairs(lake_list) do
      local fluid = lake.resource
      if data.raw["fluid"][fluid] then
        local tile_name = "randputf-lac-" .. fluid
        local ctl_name = "randputf-lac-ctl-" .. i
        table.insert(lake_ctls, {
          type = "autoplace-control",
          name = ctl_name,
          localised_name = {"", "[fluid=" .. fluid .. "] ", {"fluid-name." .. fluid}},
          richness = true,
          -- catégorie "resource" (pas "terrain") pour que les lacs (fluides
          -- INFINIS, « non quantifiables ») apparaissent dans la liste des
          -- ressources du menu de génération de carte, comme les patchs.
          category = "resource",
          order = "b-no-resource-regular",
        })
        if not lake_tiles[tile_name] then
          lake_borders[tile_name] = true
          local fc = data.raw["fluid"][fluid]
          local base = fc.base_color or {1, 0, 0}
          -- Couleur visible sur la carte ET au sol.
          local color = lake_color(fluid, base)
          local new_tile = table.deepcopy(tile_template)
          new_tile.name = tile_name
          new_tile.fluid = fluid
          new_tile.order = "a-water-zz-" .. i
          -- Couleur : l'eau vanilla se colore par le shader (`effect` natif + effect_color).
          -- On garde `effect` et on aligne effect_color/map_color sur le fluide.
          new_tile.effect_color = {
            math.floor(color[1] * 255 + 0.5),
            math.floor(color[2] * 255 + 0.5),
            math.floor(color[3] * 255 + 0.5),
          }
          new_tile.effect_color_secondary = new_tile.effect_color
          new_tile.map_color = {
            math.floor(color[1] * 255 + 0.5),
            math.floor(color[2] * 255 + 0.5),
            math.floor(color[3] * 255 + 0.5),
          }
          -- Berges : bordure sable/herbe portée par les tuiles de TERRE voisines
          -- via transitions[].to_tiles (ajouté au patch plus bas).
          local has_border = lake_borders[tile_name]
          -- Tuiles-par-fluide jamais posées par le mapgen : autoplace=0, cible
          -- de `surface.set_tiles` au runtime (flood-fill).
          new_tile.autoplace = { probability_expression = 0 }
          -- Lac sans bordure : coupe nette (transitions vidées).
          if not has_border then
            new_tile.transitions = nil
            new_tile.transitions_between_transitions = nil
            if new_tile.variants then
              new_tile.variants.empty_transitions = true
            end
          end
          lake_ctl_map[tile_name] = ctl_name
          lake_tiles[tile_name] = new_tile
        end
      end
    end

    local lake_array = {}
    for _, tile in pairs(lake_tiles) do
      table.insert(lake_array, tile)
    end

    ok, err = pcall(data.extend, data, lake_ctls)
    if ok then
      log("[randputF] created " .. #lake_ctls .. " lake autoplace controls")
    else
      log("[randputF] FAIL lake autoplace controls: " .. tostring(err))
    end
    ok, err = pcall(data.extend, data, lake_array)
    if ok then
      log("[randputF] created " .. #lake_array .. " lake tiles")
    else
      log("[randputF] FAIL lake tiles: " .. tostring(err))
    end

    -- Berges : ajoute les lacs `lake_borders` aux to_tiles des tuiles de terre.
    -- Couverture complète sur les 7 water_tiles ; `bordered` trié pour un data-stage déterministe.
    local bordered = {}
    for _, t in pairs(data.raw.tile) do
      if t.name and lake_borders[t.name] then
        bordered[#bordered + 1] = t.name
      end
    end
    table.sort(bordered)
    if #bordered > 0 then
      local patched = 0
      for _, t in pairs(data.raw.tile) do
        local has_water_target = false
        if t.transitions then
          for _, tr in ipairs(t.transitions or {}) do
            if type(tr.to_tiles) == "table" then
              for _, tn in ipairs(tr.to_tiles) do
                if water_has[tn] then
                  has_water_target = true
                  break
                end
              end
            end
            if has_water_target then break end
          end
        end
        if has_water_target then
          for _, tr in ipairs(t.transitions) do
            if type(tr.to_tiles) == "table" then
              local saw_water = false
              for _, tn in ipairs(tr.to_tiles) do
                if water_has[tn] then
                  saw_water = true
                  break
                end
              end
              if saw_water then
                for _, bname in ipairs(bordered) do
                  local present = false
                  for _, tn in ipairs(tr.to_tiles) do
                    if tn == bname then present = true break end
                  end
                  if not present then
                    tr.to_tiles[#tr.to_tiles + 1] = bname
                  end
                end
                patched = patched + 1
              end
            end
          end
        end
      end
      local names = {}
      for _, b in ipairs(bordered) do names[#names + 1] = b end
      log("[randputF] lacs: berges sur " .. #bordered .. "/" .. #lake_array
        .. " (" .. table.concat(names, ", ") .. "), " .. patched .. " transitions patchées")
    else
      log("[randputF] lacs: 0 lac avec bordure (seed)")
    end

    -- Tuiles terrain obligatoirement inscrites aux autoplace_settings de la planète :
    -- fantôme générée par l'altitude, tuiles-par-fluide posables par set_tiles (jamais mapgen).
    local nauvis = data.raw["planet"] and data.raw["planet"].nauvis
    if nauvis and nauvis.map_gen_settings then
      local mgs = nauvis.map_gen_settings
      local tile_settings = mgs.autoplace_settings
        and mgs.autoplace_settings["tile"]
        and mgs.autoplace_settings["tile"].settings
      if tile_settings then
        local pen = mgs.property_expression_names or {}
        -- Fantôme : générée par l'altitude, inscrite telle quelle.
        if data.raw.tile[PHANTOM_TILE] then
          tile_settings[PHANTOM_TILE] = {frequency = 1, size = 1}
        end
        -- Tuiles-par-fluide : jamais générées (probabilité -inf), mais posées
        -- au runtime. Inscription indispensable pour que set_tiles les accepte.
        for _, lk in ipairs(lake_array) do
          tile_settings[lk.name] = {frequency = 1, size = 1}
          pen["tile:" .. lk.name .. ":probability"] = "randputf-no-water"
          local lctl = lake_ctl_map[lk.name]
          if lctl then
            local ctls = mgs.autoplace_controls or {}
            ctls[lctl] = {frequency = 1, size = 1, richness = 1}
            mgs.autoplace_controls = ctls
          end
        end
        mgs.property_expression_names = pen
        log("[randputF] lacs: fantome + " .. #lake_array
          .. " tuiles inscrites au mapgen nauvis (phantom générée, fluides via set_tiles)")
      else
        log("[randputF] lacs: planete nauvis SANS tile autoplace settings")
      end
    end
  end
end

-- Catégorie de combustible globale : tout brûleur accepte toute catégorie item.
-- Évite un kit donnant un combustible inutilisable (cellule nucléaire, etc.).
do
  local cats = {}
  for name in pairs(data.raw["fuel-category"] or {}) do
    cats[#cats + 1] = name
  end
  local patched = 0
  for _, proto_type in pairs(data.raw) do
    for _, proto in pairs(proto_type) do
      local es = proto.energy_source
      if type(es) == "table" and es.type == "burner" then
        es.fuel_categories = cats
        patched = patched + 1
      end
    end
  end
  log("[randputF] unified fuel categories: " .. #cats .. " categories, " .. patched .. " burners patched")
end

-- Lacs : nappes TUILES fluides, pompées SANS électricité. La pompe offshore
-- (energy_source void) pompe le fluide de la tuile directement — pas de
-- resource entity, pas d'électricité au bootstrap. Les patchs fluides (entités
-- basic-fluid posées sur terre) restent minés par pumpjack. On garde le
-- renommage/tooltip de la pompe, sans lui donner resource_categories.
do
  local offshore = data.raw["offshore-pump"] and data.raw["offshore-pump"]["offshore-pump"]
  if offshore then
    -- Tooltip générique : la pompe ne pompe plus seulement de l'eau.
    offshore.localised_name = { "randputf.offshore-pump-name" }
    offshore.localised_description = { "randputf.offshore-pump-description" }
    log("[randputF] offshore-pump named for fluid lakes (tiles, no electricity); oil patches need pumpjack")
  else
    log("[randputF] WARN offshore-pump prototype not found")
  end
end

-- Collecteur de fluid boxes (2.0, aucune forme codée en dur) :
-- fluid_box / output_fluid_box / fluid_boxes, energy_source.fluid_box,
-- burner.fuel_fluid_box.
local function collect_fluid_boxes(proto)
  local boxes = {}
  local function push(box)
    if type(box) == "table" and box.production_type then
      boxes[#boxes + 1] = box
    end
  end
  -- Boiler/heat-exchanger/generator/offshore-pump : boxes dédiées.
  if type(proto.fluid_box) == "table" then push(proto.fluid_box) end
  if type(proto.output_fluid_box) == "table" then push(proto.output_fluid_box) end
  -- Crafting machines (assembler, chemical plant, ...).
  if type(proto.fluid_boxes) == "table" then
    for _, b in pairs(proto.fluid_boxes) do push(b) end
  end
  -- Energy source fluide (generator à fluide / fusion) et fuel fluid box.
  if type(proto.energy_source) == "table" then
    if type(proto.energy_source.fluid_box) == "table" then
      push(proto.energy_source.fluid_box)
    end
    if type(proto.energy_source.output_fluid_box) == "table" then
      push(proto.energy_source.output_fluid_box)
    end
  end
  if type(proto.burner) == "table" and type(proto.burner.fuel_fluid_box) == "table" then
    push(proto.burner.fuel_fluid_box)
  end
  if #boxes == 0 then return nil end
  return boxes
end

-- Parse une Energy (factorio) en kJ : "0.2kJ", "2J", "1MJ", "5.582MW". Retourne
-- un nombre (kJ) ou nil si le format est inattendu.
local function parse_energy_kj(value)
  if type(value) == "number" then
    return value / 1000 -- les valeurs numériques sont des Joules
  end
  if type(value) ~= "string" then return nil end
  local n, unit = value:match("^(%d+%.?%d*)%s*([a-zA-Z]*)")
  if not n then return nil end
  local mult = { ["J"] = 0.001, ["kJ"] = 1, ["MJ"] = 1000, ["GJ"] = 1000000 }
  return tonumber(n) * (mult[unit] or 1)
end

-- Puissance max générateur à mode température : figée dans max_power_output
-- AVANT retrait du filtre (le générateur conserve sa capacité nominale en
-- burns_fluid). Fallback 1MW si calcul impossible.
local function compute_temp_power_cap(proto, boxes)
  local max_temp = proto.maximum_temperature
  local usage = proto.fluid_usage_per_tick
  local effectivity = proto.effectivity or 1
  for _, box in ipairs(boxes) do
    if (box.production_type == "input" or box.production_type == "input-output")
      and box.filter then
      local fluid = data.raw.fluid[box.filter]
      if fluid then
        local temp_cap = fluid.max_temperature
        if max_temp and max_temp > 0 and (not temp_cap or max_temp < temp_cap) then
          temp_cap = max_temp
        end
        local default_temp = fluid.default_temperature or 0
        local heat = parse_energy_kj(fluid.heat_capacity)
        if temp_cap and usage and heat then
          local kw = (temp_cap - default_temp) * usage * heat * effectivity * 60
          if kw > 0 then
            return string.format("%.6fkW", kw)
          end
        end
      end
      return "1000kW"
    end
  end
  return nil
end

-- Fluides génériques : aucun bâtiment n'est figé sur steam/water.
-- On retire tous les filtres des fluid boxes (aucune liste codée en dur) :
-- tout bâtiment accepte tout fluide pipable.
do
  local stripped = 0
  local entities = 0
  local described = 0
  local fixed_cats = 0
  local powered = 0
  for proto_type, protos in pairs(data.raw) do
    for _, proto in pairs(protos) do
      local boxes = collect_fluid_boxes(proto)
      if boxes then
        entities = entities + 1
        if proto.type == "generator" and proto.max_power_output == nil then
          -- Générateur sans max_power_output : on fige la puissance avant retrait du filtre
          -- (proto invalide sinon : "fluid_box must have a filter if max_power_output is nil").
          local cap = compute_temp_power_cap(proto, boxes)
          if cap then
            proto.max_power_output = cap
            powered = powered + 1
          end
        end
        local has_input = false
        local has_output = false
        for _, box in ipairs(boxes) do
          if box.filter ~= nil then
            box.filter = nil
            stripped = stripped + 1
          end
          if box.production_type == "input" then has_input = true end
          if box.production_type == "output" then has_output = true end
        end
        -- Tooltip générique : fluide arbitraire (entrée/sortie si applicable).
        if has_input and not proto.localised_description then
          if has_output then
            proto.localised_description = {"randputf.boiler-any-fluid-description"}
          else
            proto.localised_description = {"randputf.generator-any-fluid-description"}
          end
          described = described + 1
        end
        -- Boilers : ajout crafting_categories pour héberger la recette fluide→fluide.
        if proto.type == "boiler"
          and has_input and has_output
          and not (proto.crafting_categories and #proto.crafting_categories > 0)
        then
          proto.crafting_categories = {"crafting-with-fluid"}
          fixed_cats = fixed_cats + 1
        end
      end
    end
  end
  log("[randputF] generic fluids: " .. stripped
    .. " fluid-box filters cleared across " .. entities .. " entities, "
    .. described .. " tooltips made generic, "
    .. fixed_cats .. " fixed-recipe transformers made crafters, "
    .. powered .. " generator powers fixed pre-strip")
end

-- Générateurs en mode COMBUSTIBLE (burns_fluid, API 2.0) : puissance basée
-- sur fuel_value plutôt que température. Tout fluide reçoit 200kJ générique.
do
  local burners = 0
  for _, proto in pairs(data.raw.generator or {}) do
    proto.burns_fluid = true
    burners = burners + 1
  end
  local fv = 0
  for _, proto in pairs(data.raw.fluid or {}) do
    proto.fuel_value = "200kJ"
    fv = fv + 1
  end
  log("[randputF] generator burns_fluid: " .. burners .. " generators, "
    .. fv .. " fluids fueled (200kJ/unit)")
end

-- Fluides assignés par la seed : on remet le filter des fluid boxes (sauf
-- générateurs burns_fluid qui restent sans filtre) et on met à jour le tooltip.
do
  local assignments = (seed.building_fluid_assignments or {})
  local assigned_count = 0
  local entities_touched = 0
  for bld_name, fluids in pairs(assignments) do
    -- Recherche prototype : nom exact puis préfixe "randputf-", garde celui avec fluid boxes.
    local proto = nil
    local search_names = {bld_name, "randputf-" .. bld_name}
    for _, name in ipairs(search_names) do
      for _, protos in pairs(data.raw) do
        if type(protos) == "table" and protos[name] then
          local cand = protos[name]
          if collect_fluid_boxes(cand) then
            proto = cand
            break
          end
        end
      end
      if proto then break end
    end
    local boxes = proto and collect_fluid_boxes(proto)
    if boxes then
      local input_fluid = fluids.input
      local output_fluid = fluids.output
      -- Générateurs : sans filtre (brûlent tout). Boiler/heat-exchanger : filter réappliqué.
      local applies_filter = proto.type ~= "generator"
      -- Appliquer le filter sur chaque fluid box selon son production_type
      for _, box in ipairs(boxes) do
        if box.production_type == "input" and input_fluid and applies_filter then
          box.filter = input_fluid
          assigned_count = assigned_count + 1
        elseif box.production_type == "output" and output_fluid then
          box.filter = output_fluid
          assigned_count = assigned_count + 1
        end
      end
      -- Tooltip : localised_description avec {"fluid-name.", X} pour le nom du fluide.
      if input_fluid and output_fluid then
        proto.localised_description = {
          "randputf.assigned-fluid-in-out-description",
          {"", "[fluid=", input_fluid, "] ", {"fluid-name.", input_fluid}},
          {"", "[fluid=", output_fluid, "] ", {"fluid-name.", output_fluid}},
        }
      elseif input_fluid then
        proto.localised_description = {
          "randputf.assigned-fluid-in-description",
          {"", "[fluid=", input_fluid, "] ", {"fluid-name.", input_fluid}},
        }
      end
      entities_touched = entities_touched + 1
    end
  end
  if assigned_count > 0 then
    log("[randputF] building fluids: " .. assigned_count .. " fluid-box filters set"
      .. " across " .. entities_touched .. " entities from seed assignments")
  end
end

log("[randputF] data-updates.lua done")