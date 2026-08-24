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

local function dump_items()
  local out = {}
  for _, proto in pairs(prototypes.item) do
    out[proto.name] = {
      type = proto.type,
      subgroup = proto.subgroup and proto.subgroup.name or "",
      place_result = proto.place_result and proto.place_result.name or nil,
      fuel_value = fuel_value_of(proto),
    }
  end
  return out
end

local function dump_special_items()
  local out = {}
  for _, proto in pairs(prototypes.gun or {}) do
    out[proto.name] = {type = "gun"}
  end
  for _, proto in pairs(prototypes.ammo or {}) do
    out[proto.name] = {type = "ammo"}
  end
  for _, proto in pairs(prototypes.tool or {}) do
    out[proto.name] = {type = "tool"}
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
    local direction = nil
    local filter_name = nil
    pcall(function()
      direction = box.flow_direction
    end)
    pcall(function()
      if box.filter then
        filter_name = box.filter.name
      end
    end)
    if direction == "input" then
      inputs = inputs + 1
    elseif direction == "output" then
      outputs = outputs + 1
    end
    details[tostring(index)] = {
      flow_direction = direction,
      filter = filter_name,
    }
  end
  return inputs, outputs, details
end

local function string_list(list)
  local out = {}
  if list then
    for _, entry in ipairs(list) do
      if type(entry) == "string" then
        table.insert(out, entry)
      elseif type(entry) == "table" and entry.name then
        table.insert(out, entry.name)
      end
    end
  end
  return out
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
      if proto.type == "offshore-pump" then
        pcall(function()
          if proto.fluid then
            entry.pumped_fluid = proto.fluid.name
          end
        end)
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
    meta = {game_version = game.active_mods["base"]},
    items = dump_items(),
    special_items = dump_special_items(),
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
