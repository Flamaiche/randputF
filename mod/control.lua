local seed = {}
do
  local ok, loaded = pcall(require, "seed.seed")
  if ok and type(loaded) == "table" then
    seed = loaded
  end
end

local function patch_positions(count)
  local positions = {}
  local radius = 24
  for index = 1, count do
    local angle = (index / count) * math.pi * 2
    table.insert(positions, {
      x = math.floor(math.cos(angle) * radius),
      y = math.floor(math.sin(angle) * radius),
    })
    if index % 2 == 0 then
      radius = radius + 8
    end
  end
  return positions
end

local function place_patches(surface)
  local patches = (storage.randputf.seed.map or {}).patches or {}
  if #patches == 0 then
    return
  end
  local positions = patch_positions(#patches)
  for index, patch in ipairs(patches) do
    local prefix = patch.kind == "fluid" and "randputf-fluid-" or "randputf-item-"
    surface.create_entity({
      name = prefix .. patch.resource,
      position = positions[index],
      amount = patch.richness,
    })
  end
end

script.on_init(function()
  storage.randputf = {seed = seed, patches_placed = false}
  local force = game.forces.player
  force.reset_recipes()
  force.reset_technologies()
  for _, tech_name in ipairs(seed.free_researches or {}) do
    local tech = force.technologies[tech_name]
    if tech then
      tech.researched = true
      for _, effect in ipairs(tech.effects or {}) do
        if effect.type == "unlock-recipe" then
          force.recipes[effect.recipe].enabled = true
        end
      end
    end
  end
end)

script.on_event(defines.events.on_player_created, function(event)
  local player = game.get_player(event.player_index)
  for _, entry in ipairs(storage.randputf.seed.starter_kit or {}) do
    player.insert({name = entry.name, count = entry.count})
  end
end)

script.on_event(defines.events.on_chunk_generated, function(event)
  if event.surface.index ~= 1 then
    return
  end
  for _, entity in ipairs(event.surface.find_entities_filtered({type = "resource", area = event.area})) do
    if string.sub(entity.name, 1, 9) ~= "randputf-" then
      entity.destroy()
    end
  end
  local left_top = event.area.left_top
  if not storage.randputf.patches_placed and left_top.x < 0 and left_top.y < 0 and left_top.x > -64 and left_top.y > -64 then
    place_patches(event.surface)
    storage.randputf.patches_placed = true
  end
end)
