local seed = {}
do
  local ok, loaded = pcall(require, "seed.seed")
  if ok and type(loaded) == "table" then
    seed = loaded
  end
end

data:extend({
  {
    type = "item-subgroup",
    name = "randputf",
    group = "intermediate-products",
    order = "z-randputf",
  },
})

local pools = seed.pools or {}
local item_template = data.raw.resource["iron-ore"]
local fluid_template = data.raw.resource["crude-oil"]

for _, name in ipairs(pools.item_resources or {}) do
  local proto = table.deepcopy(item_template)
  proto.name = "randputf-item-" .. name
  proto.autoplace = nil
  proto.localised_name = {"", name}
  proto.minable = {
    mining_time = 1,
    results = {{type = "item", name = name, amount = 1}},
  }
  data:extend({proto})
end

for _, name in ipairs(pools.fluid_resources or {}) do
  local proto = table.deepcopy(fluid_template)
  proto.name = "randputf-fluid-" .. name
  proto.autoplace = nil
  proto.localised_name = {"", name}
  proto.minable = {
    mining_time = 1,
    results = {{type = "fluid", name = name, amount = 10}},
  }
  data:extend({proto})
end

for _, recipe_seed in ipairs(seed.recipes or {}) do
  local ingredients = {}
  for _, ingredient in ipairs(recipe_seed.ingredients or {}) do
    table.insert(ingredients, {
      type = ingredient.type or "item",
      name = ingredient.name,
      amount = ingredient.amount,
    })
  end
  local results = {}
  for _, result in ipairs(recipe_seed.results or {}) do
    table.insert(results, {
      type = result.type or "item",
      name = result.name,
      amount = result.amount,
    })
  end
  data:extend({
    {
      type = "recipe",
      name = recipe_seed.name,
      enabled = recipe_seed.enabled == true,
      subgroup = "randputf",
      category = recipe_seed.category,
      energy_required = recipe_seed.energy or 0.5,
      ingredients = ingredients,
      results = results,
    },
  })
end

local tech_template = data.raw.technology["automation"]

for _, tech_seed in ipairs(seed.technologies or {}) do
  local proto = table.deepcopy(tech_template)
  proto.name = tech_seed.id
  proto.localised_name = {"", tostring(tech_seed.localised_name or tech_seed.id)}
  proto.prerequisites = {}
  for _, prereq in ipairs(tech_seed.prerequisites or {}) do
    table.insert(proto.prerequisites, prereq)
  end
  local unit_ingredients = {}
  for _, ingredient in ipairs(tech_seed.unit.ingredients or {}) do
    table.insert(unit_ingredients, {
      type = ingredient.type or "item",
      name = ingredient.name,
      amount = ingredient.amount,
    })
  end
  proto.unit = {
    count = tech_seed.unit.count,
    time = tech_seed.unit.time or 30,
    ingredients = unit_ingredients,
  }
  proto.effects = {}
  for _, effect in ipairs(tech_seed.effects or {}) do
    table.insert(proto.effects, effect)
  end
  proto.upgrade = false
  data:extend({proto})
end

if seed.meta and seed.meta.disable_vanilla_techs then
  for name, tech in pairs(data.raw.technology) do
    if string.sub(name, 1, 9) ~= "randputf-" then
      tech.enabled = false
    end
  end
end
