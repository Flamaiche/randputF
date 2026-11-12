local function fuel_value_of(proto)
  local ok, value = pcall(function()
    return proto.fuel_value
  end)
  if not ok or value == nil then
    return nil
  end
  if type(value) == "number" then
    return value
  end
  if type(value) == "table" and value.value ~= nil then
    return tonumber(value.value) or nil
  end
  return nil
end

local function stack_size_of(proto)
  -- Empilabilité réelle (source de vérité pour l'outil Python).
  local ok, size = pcall(function()
    return proto.stack_size
  end)
  if ok and type(size) == "number" then
    return size
  end
  return nil
end

local function prototypes_dict(key)
  local ok, dict = pcall(function()
    return prototypes[key]
  end)
  if ok and dict ~= nil then
    return dict
  end
  return nil
end

-- Inventaire A->Z : noms de tous les prototypes, table par table. La liste
-- des cles suit l'API LuaPrototypes (structurelle, comme un dispatch de
-- type) ; une table absente d'une version donnee est simplement omise.
local PROTOTYPE_TABLES = {
  "entity", "item", "fluid", "tile", "equipment", "damage", "virtual_signal",
  "equipment_grid", "recipe", "technology", "decorative", "particle",
  "autoplace_control", "mod_setting", "custom_input", "ammo_category",
  "named_noise_expression", "named_noise_function", "item_subgroup",
  "item_group", "fuel_category", "resource_category", "achievement",
  "module_category", "equipment_category", "trivial_smoke", "shortcut",
  "recipe_category", "quality", "surface_property", "space_location",
  "space_connection", "custom_event", "active_trigger", "asteroid_chunk",
  "collision_layer", "font", "map_gen_preset", "style",
}

local function dump_inventory()
  local out = {}
  for _, key in ipairs(PROTOTYPE_TABLES) do
    local dict = prototypes_dict(key)
    if dict then
      local names = {}
      local ok = pcall(function()
        for name in pairs(dict) do
          if type(name) == "string" then
            table.insert(names, name)
          end
        end
      end)
      if ok then
        table.sort(names)
        out[key] = names
      end
    end
  end
  return out
end

-- Tuiles : couches de collision + fluide declare. Doc du jeu sur
-- LuaTilePrototype.fluid : "The fluid offshore pump produces on this tile,
-- if any" -- donnee brute, lue par le tool pour resoudre le fluide pompe.
local function dump_tiles()
  local out = {}
  local ok_tiles, tiles = pcall(function()
    return prototypes.tile
  end)
  if not ok_tiles or tiles == nil then
    return out
  end
  for name, proto in pairs(tiles) do
    local layers = {}
    pcall(function()
      local mask = proto.collision_mask
      if mask and mask.layers then
        for layer in pairs(mask.layers) do
          if type(layer) == "string" then
            table.insert(layers, layer)
          end
        end
      end
    end)
    table.sort(layers)
    local fluid = nil
    pcall(function()
      if proto.fluid then
        fluid = proto.fluid.name
      end
    end)
    local entry = {collision_layers = layers}
    if fluid then
      entry.fluid = fluid
    end
    out[name] = entry
  end
  return out
end

local function dump_all_items()
  local out = {}
  for _, proto in pairs(prototypes.item) do
    local entry = {
      type = proto.type,
      -- Tag d'affichage : Factorio classe les packs de science en "tool",
      -- mais le rapport les presente comme des items. On garde ``type`` brut
      -- pour la logique future et on expose ``display_type`` pour l'affichage.
      display_type = "item",
      subgroup = proto.subgroup and proto.subgroup.name or "",
      place_result = proto.place_result and proto.place_result.name or nil,
      fuel_value = fuel_value_of(proto),
      stack_size = stack_size_of(proto),
    }
    -- Combustible : catégorie(s) fuel + résidu de combustion (sortie du
    -- générateur). En 2.1.20, ``fuel_category`` devient ``fuel_categories``.
    pcall(function()
      local categories = proto.fuel_categories
      if type(categories) == "table" then
        local names = {}
        for _, category in ipairs(categories) do
          table.insert(names, category)
        end
        if #names > 0 then
          entry.fuel_categories = names
          entry.fuel_category = names[1]
        end
      end
    end)
    pcall(function()
      if not entry.fuel_category and proto.fuel_category then
        entry.fuel_category = proto.fuel_category
      end
    end)
    pcall(function()
      local resid = proto.burnt_result
      if resid then
        local name = resid.name or resid
        if type(name) == "string" then
          entry.burnt_result = name
        end
      end
    end)
    -- Catégorie munition : pour caler kit de départ (arme + munitions compatibles).
    pcall(function()
      if proto.ammo_category then
        entry.ammo_category = proto.ammo_category.name
      end
    end)
    -- AttackParameters.ammo_categories : array de strings (2.0).
    pcall(function()
      local params = proto.attack_parameters
      if params and params.ammo_categories then
        entry.ammo_category = params.ammo_categories[1]
      end
    end)
    -- Produits de lancement (ItemWithInventoryPrototype, ex. satellite) :
    -- envoyer cet item en orbite produit ces items. C'est LA source de
    -- vérité des packs de science spatiale (pas le silo).
    -- NB : acces direct aux champs (pas de ref_name/probe, hors de portee
    -- lexicale ici car definis plus bas dans le fichier).
    pcall(function()
      local products = proto.rocket_launch_products
      if type(products) == "table" and #products > 0 then
        local dump_products = {}
        for _, product in ipairs(products) do
          local name = product.name or product[1]
          if type(name) == "string" then
            table.insert(dump_products, {
              name = name,
              amount = product.amount,
            })
          end
        end
        if #dump_products > 0 then
          entry.rocket_launch_products = dump_products
        end
      end
    end)
    out[proto.name] = entry
  end
  for _, key in ipairs({"gun", "ammo", "tool", "capsule", "module", "armor"}) do
    local dict = prototypes_dict(key)
    if dict then
      for _, proto in pairs(dict) do
        if not out[proto.name] then
          out[proto.name] = {
            type = proto.type,
            display_type = "item",
            subgroup = proto.subgroup and proto.subgroup.name or "",
            place_result = nil,
            fuel_value = fuel_value_of(proto),
            stack_size = stack_size_of(proto),
          }
        end
      end
    end
  end
  return out
end

local function dump_fluids()
  local out = {}
  for _, proto in pairs(prototypes.fluid) do
    out[proto.name] = {
      type = "fluid",
      display_type = "fluid",
      fuel_value = fuel_value_of(proto),
      default_temperature = proto.default_temperature,
    }
  end
  return out
end

local function fluidbox_info(proto)
  local inputs = 0
  local outputs = 0
  local details = {}
  local ok, boxes = pcall(function()
    return proto.fluidbox_prototypes
  end)
  if not ok or boxes == nil then
    return inputs, outputs, details
  end
  for index, box in ipairs(boxes) do
    local production = nil
    local filter_name = nil
    -- production_type (2.0) ; flow_direction (ancien nom 1.x).
    pcall(function()
      production = box.production_type or box.flow_direction
    end)
    pcall(function()
      if box.filter then
        filter_name = box.filter.name
      end
    end)
    if production == "input" then
      inputs = inputs + 1
    elseif production == "output" then
      outputs = outputs + 1
    elseif production == "input-output" then
      inputs = inputs + 1
      outputs = outputs + 1
    end
    details[tostring(index)] = {
      production_type = production,
      filter = filter_name,
    }
  end
  return inputs, outputs, details
end

local function string_list(list)
  -- Gere arrays ET dictionnaires LuaCustomTable (cle = valeur utile).
  local out = {}
  if list then
    for key, entry in pairs(list) do
      if type(entry) == "string" then
        table.insert(out, entry)
      elseif type(entry) == "table" and entry.name then
        table.insert(out, entry.name)
      elseif type(key) == "string" then
        table.insert(out, key)
      end
    end
  end
  return out
end

-- En 2.0 il n'y a PAS de propriete generique energy_source : chaque type
-- d'energie a sa propre propriete, et ces objets n'exposent pas de champ
-- "type". On sonde donc chaque nom et on deduit le type de la cle trouvee.
local ENERGY_SOURCE_PROPS = {
  {name = "burner_prototype", type = "burner"},
  {name = "electric_energy_source_prototype", type = "electric"},
  {name = "fluid_energy_source_prototype", type = "fluid"},
  {name = "heat_energy_source_prototype", type = "heat"},
  {name = "void_energy_source_prototype", type = "void"},
}

local function energy_source_info(proto)
  local info = {}
  local matched_type = nil
  local source = nil
  for _, probe in ipairs(ENERGY_SOURCE_PROPS) do
    local ok, value = pcall(function()
      return proto[probe.name]
    end)
    if ok and value ~= nil then
      source = value
      matched_type = probe.type
      break
    end
  end
  if source == nil then
    return info
  end
  info.type = matched_type
  local ok_fuel, categories = pcall(function()
    return source.fuel_categories
  end)
  if ok_fuel and categories then
    info.fuel_categories = string_list(categories)
  end
  -- Production electrique (panneaux solaires : pas de max_power_output).
  local ok_prod, production = pcall(function()
    return source.production
  end)
  if ok_prod and production and production > 0 then
    info.production = production
  end
  return info
end

-- Chaque entité décrite par ses capacités (classement outil Python).
local function probe(proto, prop)
  local ok, value = pcall(function()
    return proto[prop]
  end)
  if ok then
    return value
  end
  return nil
end

local function non_empty(list)
  return list and #list > 0 and list or nil
end

-- Nom d'une reference : chaine brute ou prototype portant .name. Renvoie nil si
-- l'objet ne porte pas de nom exploitable (jamais d'erreur).
local function ref_name(value)
  if type(value) == "string" then
    return value
  end
  local name = probe(value, "name")
  if type(name) == "string" then
    return name
  end
  return nil
end

-- Il n'existe aucune propriete booleenne « auto-select » : l'interface se deduit
-- de la capacite. Une machine de craft n'expose le SELECTEUR de recette (choix
-- manuel du joueur) que si c'est une assembling-machine SANS recette figee.
-- Toutes les autres -- fours, silo, assembleuses a fixed_recipe, ajouts moddes --
-- recoivent leur recette sans intervention du joueur : soit une recette unique,
-- soit l'auto-selection d'apres l'item insere (a ingredients egaux, c'est la
-- PREMIERE recette du prototype qui gagne). On ne code donc AUCUN nom d'entite
-- en dur : on teste la presence du selecteur sur l'interface CraftingMachine.
-- Les entites non posables (personnage : menu de craft) sont exclues.
local function auto_selects_recipe(proto)
  if probe(proto, "items_to_place_this") == nil then
    return false
  end
  if proto.type == "assembling-machine" and probe(proto, "fixed_recipe") == nil then
    return false
  end
  return true
end

local function dump_entities()
  local out = {}
  for _, proto in pairs(prototypes.entity) do
    local entry = {type = proto.type}

    -- Capacite de transformation : categories de craft supportees.
    local cats = non_empty(string_list(probe(proto, "crafting_categories")))
    if cats then
      entry.crafting_categories = cats
      local count = probe(proto, "ingredient_count")
      if count then
        entry.ingredient_count = count
      end
      -- Selection automatique de la recette (voir auto_selects_recipe).
      if auto_selects_recipe(proto) then
        entry.auto_select = true
      end
      -- Vitesse de craft : necessaire au rapport de complexite
      -- (temps reel = energy / crafting_speed). En 2.1 la valeur n'est pas
      -- exposee comme champ : c'est la methode get_crafting_speed().
      local ok_speed, speed = pcall(function()
        return proto.get_crafting_speed()
      end)
      if ok_speed and speed then
        entry.crafting_speed = speed
      end
    end

    -- Capacite d'extraction : categories de ressources minables.
    local rescats = non_empty(string_list(probe(proto, "resource_categories")))
    if rescats then
      entry.resource_categories = rescats
      local speed = probe(proto, "mining_speed")
      if speed then
        entry.mining_speed = speed
      end
    end

    -- Ressource (gisement) ou arbre : proprietes de minage (temps, produits,
    -- fluide requis). Le dump ne garde sinon que le type seul et l'outil
    -- Python devrait deviner temps et rendement : on exporte la source de
    -- verite (les arbres donnent le bois, minage a la main).
    if proto.type == "resource" or proto.type == "tree" then
      local props = probe(proto, "mineable_properties")
      if props then
        local products = {}
        local raw_products = probe(props, "products")
        if raw_products then
          pcall(function()
            for _, product in ipairs(raw_products) do
              table.insert(products, {
                type = probe(product, "type"),
                name = ref_name(probe(product, "name")),
                amount = probe(product, "amount"),
              })
            end
          end)
        end
        entry.mineable_properties = {
          minable = probe(props, "minable"),
          mining_time = probe(props, "mining_time"),
          required_fluid = ref_name(probe(props, "required_fluid")),
          fluid_amount = probe(props, "fluid_amount"),
          products = products,
        }
      end
    end

    -- Capacite de pompage (offshore-pump, pump). En 2.1, ``pumping_speed``
    -- peut etre absent : on expose quand meme le fluide pompe.
    local pspeed = probe(proto, "pumping_speed")
    if pspeed then
      entry.pumping_speed = pspeed
    end
    -- Fluide pompe DEPUIS LA CARTE : offshore-pump uniquement. Une vraie
    -- source (comme un gisement), pas un convertisseur : la chaudiere ou la
    -- machine a vapeur portent aussi un fluide mais ne pompent rien.
    -- Fluides : boites d'entree/sortie avec filtres eventuels.
    local inputs, outputs, details = fluidbox_info(proto)
    if inputs > 0 or outputs > 0 then
      entry.fluidboxes = {input = inputs, output = outputs, detail = details}
    end

    -- Regles de placement sur tuiles (couches requises/collident), brutes :
    -- la resolution du fluide pompe par tuiles se fait cote Python.
    local rules = {}
    local ok_rules = pcall(function()
      local raw_rules = proto.tile_buildability_rules
      if raw_rules then
        for _, rule in ipairs(raw_rules) do
          local required = {}
          local colliding = {}
          if rule.required_tiles and rule.required_tiles.layers then
            for layer in pairs(rule.required_tiles.layers) do
              if type(layer) == "string" then
                table.insert(required, layer)
              end
            end
          end
          if rule.colliding_tiles and rule.colliding_tiles.layers then
            for layer in pairs(rule.colliding_tiles.layers) do
              if type(layer) == "string" then
                table.insert(colliding, layer)
              end
            end
          end
          table.sort(required)
          table.sort(colliding)
          local r = {required_tiles = required, colliding_tiles = colliding}
          if rule.remove_on_collision then
            r.remove_on_collision = true
          end
          table.insert(rules, r)
        end
      end
    end)
    if ok_rules and #rules > 0 then
      entry.tile_buildability_rules = rules
    end

    -- Energie consommee : source (burner/electric/fluid/heat/void) + usage.
    local esrc = energy_source_info(proto)
    if esrc.type then
      entry.energy_source = esrc
    end
    local eusage = probe(proto, "energy_usage")
    if eusage then
      entry.energy_usage = eusage
    end

    -- Energie produite : generateurs (max_power_output) + panneaux solaires (get_max_energy_production).
    local pwr = probe(proto, "max_power_output")
    if pwr == nil then
      local ok, value = pcall(function()
        return proto.get_max_power_output()
      end)
      pwr = ok and value or nil
    end
    if pwr == nil then
      local ok, value = pcall(function()
        return proto.get_max_energy_production()
      end)
      pwr = ok and value or nil
    end
    if pwr and pwr > 0 then
      entry.max_power_output = pwr
    end
    if probe(proto, "heat_buffer_prototype") then
      entry.has_heat_output = true
    end

    -- Poteaux : supply_area_distance (méthode 2.0).
    local ok_supply, supply = pcall(function()
      return proto.get_supply_area_distance()
    end)
    if ok_supply and supply then
      entry.supply_area_distance = supply
    end

    -- Toute entité conservée (l'outil Python classe les "other").

    -- Chaudiere : temperature cible sans categorie de craft.
    local target_temp = probe(proto, "target_temperature")
    if target_temp then
      entry.target_temperature = target_temp
    end

    -- Science : entrées de lab.
    local labs = non_empty(string_list(probe(proto, "lab_inputs")))
    if labs then
      entry.lab_inputs = labs
    end

    -- Victoire : silo orbital.
    local rpr = probe(proto, "rocket_parts_required")
    if rpr then
      entry.rocket_parts_required = rpr
    end

    -- Produits d'un lancement : le silo ne passe pas par une recette, donc la
    -- sortie (ex. packs de science spatiale) doit venir du prototype. On sonde
    -- les noms connus ; si aucun n'existe, l'outil Python garde sa constante.
    if proto.type == "rocket-silo" then
      local launch_products = {}
      for _, prop in ipairs({"rocket_launch_products", "rocket_products"}) do
        local list = probe(proto, prop)
        if list then
          pcall(function()
            for _, product in ipairs(list) do
              table.insert(launch_products, {
                type = probe(product, "type"),
                name = ref_name(probe(product, "name")),
                amount = probe(product, "amount"),
              })
            end
          end)
          if #launch_products > 0 then
            break
          end
        end
      end
      if #launch_products > 0 then
        entry.rocket_launch_products = launch_products
      end
    end

    -- Lien inverse : quels items placent cette entite.
    local itp = probe(proto, "items_to_place_this")
    if itp then
      local names = {}
      for _, item in ipairs(itp) do
        table.insert(names, item.name)
      end
      if #names > 0 then
        entry.items_to_place_this = names
      end
    end

    out[proto.name] = entry
  end
  return out
end

local function dump_recipes()
  local out = {}
  for _, proto in pairs(prototypes.recipe) do
    local ingredients = {}
    for _, ingredient in ipairs(proto.ingredients) do
      table.insert(ingredients, {type = ingredient.type, name = ingredient.name, amount = ingredient.amount})
    end
    local products = {}
    for _, product in ipairs(proto.products) do
      table.insert(products, {type = product.type, name = product.name, amount = product.amount})
    end
    -- 2.1 n'expose pas toujours ``category`` sur LuaRecipePrototype : on
    -- sonde sans erreur, puis on retombe sur ``categories`` ou "crafting".
    local category = probe(proto, "category")
    if category == nil then
      local categories = probe(proto, "categories")
      if categories and #categories > 0 then
        category = categories[1]
      end
    end
    out[proto.name] = {
      category = category or "crafting",
      energy = proto.energy,
      ingredients = ingredients,
      products = products,
    }
  end
  return out
end

-- Arbre de recherche vanilla : coût des packs (unit), prérequis et effets.
-- Sert de RÉFÉRENCE (baseline) pour comparer la difficulté d'une seed
-- randomisée (mêmes champs que ``seed["technologies"]`` côté outil Python).
local function dump_technologies()
  local out = {}
  for _, proto in pairs(prototypes.technology) do
    local entry = {}
    -- Le runtime n'expose PAS TechnologyUnit : ni `unit`, ni `unit.time`. On
    -- lit les trois champs à plat (research_unit_*). `time` est mappé sur
    -- l'énergie par unité (research_unit_energy) : seule notion de coût
    -- unitaire disponible au runtime (le calcul de difficulté n'en dépend pas).
    local unit_count = probe(proto, "research_unit_count")
    local unit_energy = probe(proto, "research_unit_energy")
    local unit_ings = probe(proto, "research_unit_ingredients")
    if unit_count ~= nil or unit_energy ~= nil or unit_ings ~= nil then
      local ingredients = {}
      if unit_ings then
        for _, ing in ipairs(unit_ings) do
          table.insert(ingredients, {
            type = probe(ing, "type"),
            name = probe(ing, "name"),
            amount = probe(ing, "amount"),
          })
        end
      end
      entry.unit = {
        count = unit_count,
        time = unit_energy,
        ingredients = ingredients,
      }
    end
    -- `prerequisites` est un DICTIONNAIRE nom→prototype au runtime (pas un
    -- tableau) : les CLÉS sont les identifiants de techno.
    local prereq_map = probe(proto, "prerequisites")
    if prereq_map then
      local prereqs = {}
      for name in pairs(prereq_map) do
        if type(name) == "string" then
          table.insert(prereqs, name)
        end
      end
      if #prereqs > 0 then
        entry.prerequisites = prereqs
      end
    end
    local effects = {}
    local list = probe(proto, "effects")
    if list then
      for _, eff in ipairs(list) do
        table.insert(effects, {
          type = probe(eff, "type"),
          recipe = ref_name(probe(eff, "recipe")),
          technology = ref_name(probe(eff, "technology")),
          item = ref_name(probe(eff, "item")),
        })
      end
    end
    if #effects > 0 then
      entry.effects = effects
    end
    -- Déclencheur de recherche (craft-item, mine-entity, send-item-to-orbit…).
    -- Les champs varient selon le type : on garde tout ce qui existe, sinon
    -- les techs « mine-entity » perdent leur cible (ex. uranium-mining).
    local trigger = probe(proto, "research_trigger")
    if type(trigger) == "table" then
      local trig = {type = trigger.type}
      local item = trigger.item
      if type(item) == "string" then
        trig.item = item
      elseif type(item) == "table" then
        trig.item = item.name or item[1]
      end
      local count = trigger.count
      if type(count) == "number" then
        trig.count = count
      elseif type(count) == "table" then
        trig.count = count.min or count[1] or 1
      end
      if type(trigger.entities) == "table" then
        local entities = {}
        for _, name in ipairs(trigger.entities) do
          if type(name) == "string" then
            table.insert(entities, name)
          end
        end
        trig.entities = entities
      end
      if type(trigger.fluid) == "string" then
        trig.fluid = trigger.fluid
      end
      if type(trigger.amount) == "number" then
        trig.amount = trigger.amount
      end
      local entity = trigger.entity
      if type(entity) == "string" then
        trig.entity = entity
      elseif type(entity) == "table" then
        trig.entity = entity.name or entity[1]
      end
      entry.research_trigger = trig
    end
    out[proto.name] = entry
  end
  return out
end

script.on_init(function()
  -- Garde-fou : un export depuis une partie où randputF est actif écrirait un
  -- dump pollué — recettes randputf-* ajoutées, mais surtout des valeurs
  -- vanilla MUTÉES en place (fuel_value 0 → 200 000 sur les fluides, filtres,
  -- fuel_categories) qui ressemblent à du contenu légitime. La présence d'une
  -- seule recette préfixée suffit à détecter la data-stage randomisée. Refus
  -- net : aucun fichier écrit, log explicite.
  local ok_recipes, recipes = pcall(function()
    return prototypes.recipe
  end)
  -- Préfixe partagé avec le tool Python (tool/parsers/vanilla.py,
  -- _RANDPUTF_PREFIX). Toute modification ici doit être répercutée là-bas et
  -- inversement.
  local RANDPUTF_PREFIX = "randputf-"
  local artefact = nil
  if ok_recipes and recipes then
    for name in pairs(recipes) do
      if type(name) == "string" and name:sub(1, #RANDPUTF_PREFIX) == RANDPUTF_PREFIX then
        artefact = name
        break
      end
    end
  end
  if artefact then
    log("randputF exporter: EXPORT REFUSE — data-stage randomisee par randputF (recette «" .. artefact .. " »). Desactive randputF puis relance une partie pour un dump vanilla propre.")
    return
  end

  local payload = {
    meta = {game_version = script.active_mods["base"]},
    inventory = dump_inventory(),
    tiles = dump_tiles(),
    items = dump_all_items(),
    fluids = dump_fluids(),
    entities = dump_entities(),
    recipes = dump_recipes(),
    technologies = dump_technologies(),
  }
  local ok, err = pcall(function()
    helpers.write_file("randputF/vanilla_dump.json", helpers.table_to_json(payload))
  end)
  if ok then
    log("randputF exporter: vanilla_dump.json écrit")
  else
    log("randputF exporter: échec d'écriture: " .. tostring(err))
  end
end)
