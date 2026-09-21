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

-- Recherche d'entité par nom dans toutes les tables data.raw.
local function find_entity_proto(name)
  if not name then return nil end
  for _, table_proto in pairs(data.raw) do
    if type(table_proto) == "table" and table_proto[name] then
      return table_proto[name]
    end
  end
  return nil
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
  local main_product = nil
  for _, result in ipairs(recipe_seed.results or {}) do
    table.insert(results, {
      type = result.type or "item",
      name = result.name,
      amount = result.amount,
    })
    if not main_product then main_product = result end
  end

  local subgroup = "randputf"
  local order = ""
  if main_product and main_product.type == "item" then
    -- Sous-groupe d'inventaire hérité du proto produit (item-like inclus).
    local item_proto = find_item_proto(main_product.name)
    if item_proto then
      subgroup = item_proto.subgroup or subgroup
      order = item_proto.order or ""
    end
  elseif main_product and main_product.type == "fluid" then
    subgroup = "fluid"
    order = ""
  end

  local recipe_def = {
      type = "recipe",
      name = recipe_seed.name,
      localised_name = {"", (recipe_seed.name:gsub("^randputf%-", ""):gsub("-", " "))},
      enabled = recipe_seed.enabled == true,
      subgroup = subgroup,
      order = order,
      energy_required = recipe_seed.energy or 0.5,
      ingredients = ingredients,
      results = results,
    }
    if recipe_seed.category and data.raw["recipe-category"][recipe_seed.category] then
      recipe_def.category = recipe_seed.category
    end
    -- crafted_in : restreint la recette au bâtiment précis (2.0).
    if recipe_seed.crafted_in then
      recipe_def.crafted_in = {recipe_seed.crafted_in}
      -- Bâtiment sans crafting_category → ajout de la catégorie nécessaire.
      local crafter = find_entity_proto(recipe_seed.crafted_in)
      if crafter then
        local cats = crafter.crafting_categories or {}
        local needed = recipe_def.category or "crafting"
        local has_cat = false
        for _, c in ipairs(cats) do
          if c == needed then has_cat = true break end
        end
        if not has_cat then
          crafter.crafting_categories = cats
          table.insert(crafter.crafting_categories, needed)
        end
      end
    end
    data:extend({recipe_def})
end

local tech_template = data.raw.technology["automation"]

-- Icônes tech : grille 2x2 max 4 icônes des items débloqués.
local ICON_OUTPUT_SIZE = 64 -- taille d'affichage par icône sur le canvas 128
local icon_layouts = {
  {1, {{0, 0}}},
  {2, {{-32, 0}, {32, 0}}},
  {3, {{-32, 32}, {32, 32}, {0, -32}}},
  {4, {{-32, -32}, {32, -32}, {-32, 32}, {32, 32}}},
}

local function proto_icon(proto)
  if not proto then return nil end
  if proto.icons and #proto.icons > 0 then
    return {icon = proto.icons[1].icon, icon_size = proto.icons[1].icon_size or proto.icon_size}
  end
  if proto.icon then
    return {icon = proto.icon, icon_size = proto.icon_size}
  end
  return nil
end

local function tech_icons_for_effects(effects)
  local picked = {}
  for _, effect in ipairs(effects or {}) do
    if effect.type ~= "unlock-recipe" then goto continue end
    local recipe = data.raw.recipe[effect.recipe]
    if recipe then
      for _, result in ipairs(recipe.results or {}) do
        local proto = (result.type == "fluid") and data.raw.fluid[result.name]
          or find_item_proto(result.name)
        local ic = proto_icon(proto)
        if ic then
          table.insert(picked, ic)
          if #picked >= 4 then break end
        end
      end
    end
    ::continue::
  end
  if #picked == 0 then return nil end

  local count = math.min(#picked, 4)
  local shifts = nil
  for _, layout in ipairs(icon_layouts) do
    if layout[1] == count then shifts = layout[2] end
  end
  local icons = {}
  for i = 1, count do
    local ic = picked[i]
    local source = ic.icon_size or 64
    table.insert(icons, {
      icon = ic.icon,
      icon_size = source,
      scale = ICON_OUTPUT_SIZE / source,
      shift = {shifts[i][1], shifts[i][2]},
    })
  end
  return icons
end

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
    table.insert(unit_ingredients, {ingredient.name, ingredient.amount})
  end
  proto.unit = {
    count = tech_seed.unit.count,
    time = tech_seed.unit.time or 30,
    ingredients = unit_ingredients,
  }
  -- research_trigger : déblocage par craft manuel de l'item déclencheur.
  if tech_seed.craft_trigger then
    proto.unit = {
      count = 1,
      time = 1,
      ingredients = {},
    }
    proto.research_trigger = {
      type = "craft-item",
      item = tech_seed.craft_trigger,
      count = tech_seed.craft_trigger_count or 1,
    }
    proto.enabled = true
  end
  proto.effects = {}
  for _, effect in ipairs(tech_seed.effects or {}) do
    table.insert(proto.effects, effect)
  end
  -- Icônes des items/recettes DÉBLOQUÉS (visible sur le nœud de tech).
  local icons = tech_icons_for_effects(proto.effects)
  if icons then
    proto.icon = nil
    proto.icons = icons
  end
  proto.upgrade = false
  proto.level = nil
  proto.max_level = nil
  data:extend({proto})
end

if seed.meta and seed.meta.disable_vanilla_techs then
  for name, tech in pairs(data.raw.technology) do
    if string.sub(name, 1, 9) ~= "randputf-" then
      tech.enabled = false
    end
  end
end
