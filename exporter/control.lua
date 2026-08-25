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

local function prototypes_dict(key)
  local ok, dict = pcall(function()
    return prototypes[key]
  end)
  if ok and dict ~= nil then
    return dict
  end
  return nil
end

local function dump_all_items()
  local out = {}
  for _, proto in pairs(prototypes.item) do
    local entry = {
      type = proto.type,
      subgroup = proto.subgroup and proto.subgroup.name or "",
      place_result = proto.place_result and proto.place_result.name or nil,
      fuel_value = fuel_value_of(proto),
    }
    -- Categorie de munitions : cote munition ET cote arme, pour caler
    -- le kit de depart (arme + munitions compatibles).
    pcall(function()
      if proto.ammo_category then
        entry.ammo_category = proto.ammo_category.name
      end
    end)
    pcall(function()
      local params = proto.attack_parameters
      if params and params.ammo_category then
        entry.ammo_category = params.ammo_category.name
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
            subgroup = proto.subgroup and proto.subgroup.name or "",
            place_result = nil,
            fuel_value = fuel_value_of(proto),
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
      fuel_value = fuel_value_of(proto),
      default_temperature = proto.default_temperature,
    }
  end
  return out
end

local function energy_source_info(proto)
  local info = {}
  local ok, source = pcall(function()
    return proto.energy_source
  end)
  if not ok or source == nil then
    return info
  end
  local ok_type, source_type = pcall(function()
    return source.type
  end)
  if ok_type then
    info.type = source_type
  end
  if source_type == "burner" then
    local ok_fuel, categories = pcall(function()
      return source.fuel_categories
    end)
    if ok_fuel and categories then
      local list = {}
      for _, category in ipairs(categories) do
        table.insert(list, category)
      end
      info.fuel_categories = list
    end
  end
  return info
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
    -- 2.0 : production_type ("input", "output", "input-output") ;
    -- flow_direction etait l'ancien nom 1.x.
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

local function first_ok(proto, names)
  for _, n in ipairs(names) do
    local ok, value = pcall(function()
      return proto[n]
    end)
    if ok and value ~= nil then
      return value
    end
  end
  return nil
end

local function crafting_categories_of(proto)
  local ok, categories = pcall(function()
    return proto.crafting_categories
  end)
  if ok then
    return categories
  end
  return nil
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
  return info
end

local EXTRACTOR_TYPES = {
  ["mining-drill"] = true,
  ["offshore-pump"] = true,
}
local TRANSFORMER_TYPES = {
  ["assembling-machine"] = true,
  ["furnace"] = true,
  ["chemical-plant"] = true,
  ["oil-refinery"] = true,
  ["boiler"] = true,
  ["lab"] = true,
  ["rocket-silo"] = true,
}
local GENERATOR_TYPES = {
  ["generator"] = true,
  ["solar-panel"] = true,
  ["reactor"] = true,
  ["burner-generator"] = true,
}

local function dump_entities()
  local out = {}
  for _, proto in pairs(prototypes.entity) do
    local interesting = EXTRACTOR_TYPES[proto.type] or TRANSFORMER_TYPES[proto.type] or GENERATOR_TYPES[proto.type]
    local inputs, outputs, fluidboxes = fluidbox_info(proto)
    if interesting or inputs > 0 or outputs > 0 then
      local entry = {
        type = proto.type,
        crafting_categories = string_list(crafting_categories_of(proto)),
        energy_source = energy_source_info(proto),
        fluidboxes = {input = inputs, output = outputs, detail = fluidboxes},
      }
      if EXTRACTOR_TYPES[proto.type] then
        pcall(function()
          entry.resource_categories = string_list(proto.resource_categories)
        end)
      end
      -- Slots de craft : nombre max d'ingredients supportes (2.0).
      pcall(function()
        if proto.ingredient_count then
          entry.ingredient_count = proto.ingredient_count
        end
      end)
      -- Consommation de science packs du lab.
      pcall(function()
        if proto.lab_inputs then
          entry.lab_inputs = string_list(proto.lab_inputs)
        end
      end)
      pcall(function()
        if proto.rocket_parts_required then
          entry.rocket_parts_required = proto.rocket_parts_required
        end
      end)
      pcall(function()
        if proto.energy_usage then
          entry.energy_usage = proto.energy_usage
        end
      end)
      if proto.type == "offshore-pump" then
        local fluid = first_ok(proto, {"fluid"})
        pcall(function()
          if fluid then
            entry.pumped_fluid = fluid.name
          end
        end)
      end
      if TRANSFORMER_TYPES[proto.type] then
        local cats = entry.crafting_categories or {}
        if #cats == 0 then
          log("randputF exporter: aucune categorie de craft pour " .. proto.name)
        end
      end
      out[proto.name] = entry
    end
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
    out[proto.name] = {
      category = proto.category,
      energy = proto.energy,
      ingredients = ingredients,
      products = products,
    }
  end
  return out
end

script.on_init(function()
  local payload = {
    meta = {game_version = script.active_mods["base"]},
    items = dump_all_items(),
    fluids = dump_fluids(),
    entities = dump_entities(),
    recipes = dump_recipes(),
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
