-- data-updates.lua — resource entities: minerai, oil
-- Native Factorio resource autoplace via core lualib resource-autoplace.

local resource_autoplace = require("resource-autoplace")

local seed = {}
do
  local ok, loaded = pcall(require, "seed.seed")
  if ok and type(loaded) == "table" then
    seed = loaded
  end
end

log("[randputF] data-updates.lua start")

-- Ré-armement des véhicules selon la graine (§7/§12.1). La randomisation des
-- armes montées est APPLIQUÉE aux prototypes d'entités : la seed assigne à
-- chaque véhicule armé 1..N armes (`seed.vehicle_armament`, items gun réels,
-- aucune valeur en dur), puis le mod CLONE chaque arme (« arme dans arme »)
-- pour CE véhicule et remplace l'armement vanilla de l'entité. La portée du
-- clone est augmentée selon la taille de l'entité complète (extent de sa
-- selection_box) : plus le véhicule est gros, plus l'arme porte loin.
-- On ne garde QUE les armes tirées (0 → véhicule non armé ; l'artillery-wagon
-- structurellement à tourelle unique monte la 1re). Aucun item/recette n'est
-- créé pour ces armes (jamais craftables).
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
  new_entity.localised_name = {"", (resource_name:gsub("-", " "))}

  if is_fluid then
    new_entity.minable = {
      mining_time = 1,
      results = {{ type = "fluid", name = resource_name, amount = 1 }},
    }
    new_entity.resource_category = "basic-fluid"
  else
    new_entity.minable = {
      mining_time = 1,
      results = {{ type = "item", name = resource_name, amount = 1 }},
    }
    new_entity.resource_category = "basic-solid"
  end

  new_entity.autoplace = resource_autoplace.resource_autoplace_settings{
    name = new_entity_name,
    patch_set_name = new_entity_name,
    autoplace_control_name = control_name,
    base_density = math.max(4, patch.richness * 8 / 100000),
    base_spots_per_km2 = 2,
    has_starting_area_placement = true,
    seed1 = seed_value * 1000 + i,
    additional_richness = patch.richness,
  }
  new_entity.placeable_by = nil

  local icon_src = is_fluid and data.raw["fluid"][resource_name] or data.raw["item"][resource_name]
  local icon_path, icon_size = get_primary_icon(icon_src)
  if icon_path then
    new_entity.icon = icon_path
    new_entity.icon_size = icon_size
  end
  if not is_fluid and icon_path then
    -- Minerais solides : l'icône de l'item sur le sol (stages en 4 positions).
    -- Les fluides gardent la flaque d'huile vanilla (template crude-oil).
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
    r = (math.floor((seed_value * 131 + i * 47) % 101) + 30) / 255,
    g = (math.floor((seed_value * 197 + i * 83) % 101) + 30) / 255,
    b = (math.floor((seed_value * 251 + i * 127) % 101) + 30) / 255,
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

-- ── Lacs de fluide (§7.5) : 3e type de raw ressource ─────────────────────
-- L'eau vanilla de la carte est SUPPRIMÉE (plus aucun lac généré) : seules
-- subsistent les tuiles `randputf-lac-<fluid>` tirées par la seed. Chaque
-- tuile porte le champ `fluid` = fluide tiré : une pompe offshore VANILLA
-- posée dessus débite ce fluide (volume infini, comme l'eau). Zéro lac tiré
-- = carte sans eau. Richesse = taille du lac (le volume est infini).
local lake_list = (seed.map or {}).lakes or {}
if #lake_list > 0 then
-- ── Couleur de lac (§7.5) ─────────────────────────────────────────────────
-- Recolore chaque nappe à partir du base_color de SON fluide : on conserve la
-- TEINTE (hue) vanilla mais on relève fortement saturation/luminance pour
-- que le lac soit visible sur la carte (map_color 0-255 moteur) et au sol.
-- Un simple scale du base_color serait inutilisable : le crude-oil est NOIR
-- ({0,0,0} → tuile {30,30,30}, invisible sur la minimap). Fluides sans
-- chromatisme (s ≈ 0) : teinte de secours distincte par fluide (table
-- lake_fallback_hue / lightness) pour ne pas les confondre.
local function rgb_to_hsl(r, g, b)
  local mx, mn = math.max(r, g, b), math.min(r, g, b)
  local l = (mx + mn) / 2
  local d = mx - mn
  if d < 1e-6 then
    return 0, 0, l
  end
  local s = l > 0.5 and d / (2 - mx - mn) or d / (mx + mn)
  local h
  if mx == r then
    h = (g - b) / d
  elseif mx == g then
    h = (b - r) / d + 2
  else
    h = (r - g) / d + 4
  end
  h = h / 6
  if h < 0 then h = h + 1 end
  return h, s, l
end

local function hsl_component(p, q, t)
  if t < 0 then t = t + 1 end
  if t > 1 then t = t - 1 end
  if t < 1 / 6 then return p + (q - p) * 6 * t end
  if t < 1 / 2 then return q end
  if t < 2 / 3 then return p + (q - p) * (2 / 3 - t) * 6 end
  return p
end

-- Teintes de secours pour les fluides sans chromatisme (base_color noir/blanc
-- : crude-oil, steam, hydrogen…). Sans hue propre, on attribue à CHAQUE fluide
-- dénué de hue une teinte distincte pour que ses lacs ne soient pas confondus.
local lake_fallback_hue = {
  ["crude-oil"]    = 0.06,  -- brun huile orangé
  ["steam"]        = 0.60,  -- bleu clair
  ["hydrogen"]     = 0.50,  -- cyan
  ["nitric-acid"]  = 0.83,  -- magenta
  ["sulfuric-acid"]= 0.16,
}
-- Retourne un triplet RGB POUR LA CARTE : rendu éclatant, distinct du terrain,
-- conservant la hue du fluide (ou une hue de secours si achromatique). On
-- relève fortement saturation et luminance : un simple scale du base_color est
-- inutilisable (le crude-oil noir donnerait {30,30,30}, invisible).
local function lake_color(r, g, b, fluid)
  local h, s, l = rgb_to_hsl(r, g, b)
  if s < 0.2 then
    h = lake_fallback_hue[fluid] or (l < 0.4 and 0.04 or 0.58)
  end
  local ss = 0.92
  local ll = 0.5
  local q = ll < 0.5 and ll * (1 + ss) or ll + ss - ll * ss
  local p = 2 * ll - q
  return {
    hsl_component(p, q, h + 1 / 3),
    hsl_component(p, q, h),
    hsl_component(p, q, h - 1 / 3),
  }
end

-- 1) Neutraliser l'autoplace de toutes les tuiles d'eau vanilla. On ne met
-- PAS `autoplace = nil` : le setup de la planète "nauvis" exige une spec
-- d'autoplace sur ces tuiles (erreur "does not have an autoplace
-- specification"). On impose une probabilité constante nulle — spec valide,
-- zéro tuile générée.
local water_tiles = water_tile_type_names or {}
if #water_tiles == 0 then
  water_tiles = {
    "water", "deepwater", "water-shallow", "water-green",
    "deepwater-green", "water-mud", "water-wube",
  }
end
local purged = 0
for _, tname in ipairs(water_tiles) do
  local t = data.raw.tile[tname]
  if t then
    t.autoplace = { probability_expression = 0 }
    purged = purged + 1
  end
end
-- VÉRITÉ DE FOND : l'eau vanilla n'est pas posée par l'autoplace du
-- prototype de tuile mais par un mécanisme de TERRAIN lié à l'altitude
-- (noise water_base). Le forçage `probability_expression = 0` sur le
-- prototype ne suffit pas : le mapgen conserve de l'eau (mesuré : 3053
-- tuiles water/deepwater après neutralisation prototype seule).
-- La solution qui élimine TOUTE l'eau (mesuré : 0 tuile restante) est
-- l'override du mapgen par surface : `map_gen_settings.property_expression_names`
-- en remplaçant `tile:<n>:probability` par une expression constante négative.
-- On définit l'expression une fois et on l'applique à chaque tuile d'eau pour
-- la planète nauvis (seule planète jouable du mod). Les lacs randputf ne
-- sont pas touchés : leur autoplace vient de resource_autoplace, qui n'est
-- pas référencée dans property_expression_names.
data:extend{
  { type = "noise-expression", name = "randputf-no-water", expression = "-999" },
}
do
  local nauvis = data.raw["planet"] and data.raw["planet"].nauvis
  if nauvis and nauvis.map_gen_settings then
    local pen = nauvis.map_gen_settings.property_expression_names or {}
    for _, tname in ipairs(water_tiles) do
      pen["tile:" .. tname .. ":probability"] = "randputf-no-water"
    end
    nauvis.map_gen_settings.property_expression_names = pen
  else
    log("[randputF] lacs: WARN planete nauvis introuvable — eau vanilla non neutralisée au mapgen")
  end
end
log("[randputF] lacs: eau vanilla neutralisée (" .. purged .. " tuiles)")

  local tile_template = data.raw.tile.water or data.raw.tile.deepwater
  if tile_template then
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
          localised_name = {"", {"fluid-name." .. fluid}},
          richness = true,
          category = "terrain",
          order = "b-no-resource-regular",
        })
        if not lake_tiles[tile_name] then
          local fc = data.raw["fluid"][fluid]
          local base = fc.base_color or {1, 0, 0}
          -- Couleur visible sur la carte ET au sol (§7.5) : base_color relevé
          -- en saturation/luminance (hue conservée, black/steam → défaut).
          local color = lake_color(base[1], base[2], base[3], fluid)
          local new_tile = table.deepcopy(tile_template)
          new_tile.name = tile_name
          new_tile.fluid = fluid
          new_tile.order = "a-water-zz-" .. i
          new_tile.map_color = {
            math.floor(color[1] * 200 + 30),
            math.floor(color[2] * 200 + 30),
            math.floor(color[3] * 200 + 30),
          }
          if new_tile.variants and new_tile.variants.main then
            for _, layer in ipairs(new_tile.variants.main) do
              layer.tint = {color[1], color[2], color[3], 1}
            end
          end
          -- Berges (§7.5) : 1 lac sur 2 (déterministe par seed) hérite d'une
          -- bordure sable/herbe. Les bordures des nappes sont dessinées par les
          -- tuiles de TERRE voisines via `transitions[].to_tiles` : on ajoutera
          -- ce nom de lac à la liste que celles-ci ciblent (patch plus bas).
          -- Sans cela, le lac coupe net (variants.empty_transitions, copié de
          -- water : pas de transition propre).
          new_tile.lac_border = (seed_value + i) % 2 == 0
          resource_autoplace.initialize_patch_set(tile_name, true)
          new_tile.autoplace = resource_autoplace.resource_autoplace_settings{
            name = tile_name,
            patch_set_name = tile_name,
            autoplace_control_name = ctl_name,
            order = "b-no-resource-regular",
            base_density = math.max(4, lake.richness * 8 / 100000),
            base_spots_per_km2 = 2,
            has_starting_area_placement = true,
            seed1 = seed_value * 1000 + 700 + i,
            additional_richness = lake.richness,
          }
          new_tile.lac_ctl = ctl_name
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

    -- Berges des lacs (§7.5) : les transitions sable/terre sont portées par
    -- les tuiles de TERRE (`transitions[].to_tiles`, qui cible la liste des
    -- tuiles d'eau). On ajoute ici les lacs marqués `lac_border` à ces
    -- cibles : leurs abords sont alors bordés comme une nappe vanilla, tandis
    -- que les lacs sans bordure coupent net.
    local bordered = {}
    for _, t in pairs(data.raw.tile) do
      if t.name and t.name:find("^randputf%-lac%-") then
        if t.lac_border then
          bordered[#bordered + 1] = t.name
        end
      end
    end
    if #bordered > 0 then
      local patched = 0
      for _, t in pairs(data.raw.tile) do
        local has_water_target = false
        if t.transitions then
          for _, tr in ipairs(t.transitions or {}) do
            if type(tr.to_tiles) == "table" then
              for _, tn in ipairs(tr.to_tiles) do
                if tn == "water" or tn == "deepwater" or tn == "water-green" then
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
                if tn == "water" or tn == "deepwater" or tn == "water-green" then
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

    -- Les tuiles terrain ne sont générées que si la planète les liste dans ses
    -- autoplace_settings["tile"].settings : sans cette inscription elles ne
    -- participent jamais au mapgen. On inscrit donc chaque tuile de lac (et
    -- son contrôle) auprès de nauvis, seule planète jouable du mod.
    local nauvis = data.raw["planet"] and data.raw["planet"].nauvis
    if nauvis and nauvis.map_gen_settings then
      local mgs = nauvis.map_gen_settings
      local tile_settings = mgs.autoplace_settings
        and mgs.autoplace_settings["tile"]
        and mgs.autoplace_settings["tile"].settings
      if tile_settings then
        for _, lk in ipairs(lake_array) do
          tile_settings[lk.name] = {}
          if lk.lac_ctl then
            local ctls = mgs.autoplace_controls or {}
            ctls[lk.lac_ctl] = {}
            mgs.autoplace_controls = ctls
          end
        end
        log("[randputF] lacs: " .. #lake_array .. " tuiles inscrites au mapgen nauvis")
      else
        log("[randputF] lacs: planete nauvis SANS tile autoplace settings")
      end
    end
  end
end

-- ── Catégorie de combustible GLOBALE (§8 starter kit) ────────────────────
-- Tous les brûleurs acceptent TOUTES les catégories de combustible item. La
-- seed n'a donc pas à vérifier de compatibilité : tout combustible marche
-- dans tout brûleur — un uranium-fuel-cell se brûle dans un
-- burner-mining-drill, un charbon dans un réacteur, etc.
-- Sans ce patch, un kit tirant le combustible à la plus grosse fuel_value
-- pouvait donner une cellule d'uranium (catégorie "nuclear") dans un
-- brûleur "chemical" : inutilisable (§8).
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

-- ── Lacs : les étendues fluides se pompent SANS électricité (§10) ────────
-- Les patchs fluides (lacs : pétrole brut, gaz, acide…) sont des entités
-- resource_category = "basic-fluid". En vanilla seul le pumpjack (électrique)
-- les mine — or extraire un lac ne doit pas exiger l'électricité qui ne sera
-- produite qu'APRÈS (boucle dure §10). On donne à la pompe côtière
-- (offshore-pump, énergie void, déjà sans électricité) la capacité de miner
-- ces gisements : chaque lac devient extractible dès le bootstrap.
do
  local offshore = data.raw["offshore-pump"] and data.raw["offshore-pump"]["offshore-pump"]
  if offshore then
    offshore.resource_categories = { "basic-fluid" }
    -- Le tooltip vanilla ({"entity-name.offshore-pump"} / description) laisse
    -- croire qu'on ne pompe que de l'eau. Sur cette carte Toute eau est
    -- remplacée par des nappes fluides (§7.5) : renommer la pompe et décrire
    -- sa production générique (le fluide dépend de la nappe posée dessous).
    offshore.localised_name = { "randputf.offshore-pump-name" }
    offshore.localised_description = { "randputf.offshore-pump-description" }
    log("[randputF] offshore-pump can mine basic-fluid lakes; tooltip synced (no electricity)")
  else
    log("[randputF] WARN offshore-pump prototype not found")
  end
end

log("[randputF] data-updates.lua done")