-- randputF — contrôle runtime.
--
-- Stratégie de spawn : on ne se bat PAS contre le scenario freeplay, on le
-- CONFIGURE. Le base freeplay expose des remote calls
-- `remote.call("freeplay", "set_created_items", ...)` et
-- `set_respawn_items(...)` qui définissent le kit posé au spawn/respawn. On y
-- injecte notre kit seed : le freeplay pose donc EXACTEMENT notre kit (arme +
-- munitions + machines), sans doublon ni item vanilla.
--
-- Le `on_player_created` + une purge courte ne sont gardés qu'en filet de
-- sécurité : si pour une raison quelconque (sauvegarde antérieure, ordre de
-- chargement) l'inventaire ne correspond pas au kit seed, on le corrige.
-- ____________________________________________________________________________

local seed = {}
do
  local ok, loaded = pcall(require, "seed.seed")
  if ok and type(loaded) == "table" then
    seed = loaded
  end
end

-- ____________________________________________________________________________
-- Site de crash (§7)
--
-- Le crash vanilla pose un kit fixe (munitions, plaques…) dans les conteneurs
-- `crash-site-*`. On le VIDE puis on remplit chaque slot avec `n` copies d'un
-- matériau aléatoire, où `n ∈ {0,1,2,3}` suit la loi pondérée de la seed
-- (seed.wreck.counts = [c0, c1, c2, c3], c0 > c1 > c2 > c3, 0 × c0 + 1 × c1 +
-- 2 × c2 + 3 × c3 = 100) : 0 est le plus fréquent (slot vide), 3 le plus rare.
-- Chaque conteneur n'est traité QU'UNE FOIS (marque unit_number dans storage),
-- donc le loot du joueur n'est JAMAIS écrasé au rechargement ultérieur.

local WRECK_SETTLE_TICKS = 300  -- fenêtre de balayage (world just créé)
local WRECK_SWEEP_INTERVAL = 10 -- pas du balayage pendant la fenêtre

local function init_wreck()
  storage.randputf.wreck_processed = storage.randputf.wreck_processed or {}
  if storage.randputf.wreck_stop == nil and game then
    -- `game` est NIL pendant on_load (API 2.0) : on ne peut calculer le stop
    -- qu'au runtime (on_init / premier tick). Les saves anciennes sans ce
    -- champ gardent stop à nil → pas de balayage (idempotence garantie par la
    -- marque unit_number : chaque conteneur n'est traité qu'une fois).
    storage.randputf.wreck_stop = game.tick + WRECK_SETTLE_TICKS
  end
end

-- Tirage pondéré du nombre d'items (0..3) pour un slot, depuis les comptes.
local function draw_slot_count(counts, rng)
  local total = 0
  for i = 1, 4 do
    total = total + (counts[i] or 0)
  end
  if total <= 0 then
    return 0
  end
  local roll = math.floor(rng() * total)
  for n = 0, 3 do
    roll = roll - (counts[n + 1] or 0)
    if roll < 0 then
      return n
    end
  end
  return 0
end

local function process_crash_container(entity)
  if not entity.valid then
    return
  end
  local unit = entity.unit_number
  if unit and (storage.randputf.wreck_processed or {})[unit] then
    return
  end
  local wreck = seed.wreck
  -- Un conteneur n'expose qu'un seul inventaire (index auto 1) : il n'existe
  -- pas de nommage `defines.inventory.*` dédié aux coffres vanilles.
  local inv = entity.get_inventory(1)
  if not (inv and wreck and wreck.counts) then
    return
  end
  local loot = wreck.loot or {}
  local counts = wreck.counts
  local base = (seed.meta and seed.meta.seed) or 0
  local rng = game.create_random_generator(base * 1000003 + (unit or 0))
  inv.clear()
  for i = 1, #inv do
    local n = draw_slot_count(counts, rng)
    if n > 0 and #loot > 0 then
      local mat = loot[rng(1, #loot)]
      if mat and not inv[i].valid_for_read then
        inv[i].set_stack({name = mat, count = n})
      end
    end
  end
  if unit then
    storage.randputf.wreck_processed[unit] = true
  end
  log(string.format(
    "[randputF] wreck: %s rempli (%d slots, loi %s)",
    entity.name,
    #inv,
    tostring(counts[1]) .. "," .. tostring(counts[2]) .. "," .. tostring(counts[3]) .. "," .. tostring(counts[4])
  ))
end

-- Traite les conteneurs `crash-site-*` d'une surface (ou d'une zone).
local function process_crash_site(surface, area)
  if not (surface and surface.valid) then
    return
  end
  local filter = {type = "container"}
  if area then
    filter.area = area
  end
  for _, entity in pairs(surface.find_entities_filtered(filter)) do
    if entity.valid and entity.name:find("crash-site", 1, true) then
      process_crash_container(entity)
    end
  end
end

-- Récap en chat des raw ressources de la seed : pour CHAQUE ressource on
-- marque sa provenance (d'où elle vient) en plus de son nom. 2 sources :
--   [LAC]   = lac de fluide (tuile randputf-lac-<fluide>) — volume INFINI,
--            pompé par une pompe offshore posée sur la tuile ;
--   [PATCH] = patch posé en carte à l'autoplace — pumpjack pour un fluide,
--            extraction au sol pour un item (patch kind item/fluid).
local function describe_patches()
  local lines = {}
  table.insert(lines, "[randputF] RESSOURCES DE LA SEED #" .. tostring(seed.meta and seed.meta.seed or "?"))
  for _, lake in ipairs((seed.map or {}).lakes or {}) do
    table.insert(lines, string.format(
      "  [LAC] %s (infini, richesse=%s)",
      lake.resource,
      lake.richness
    ))
  end
  for _, patch in ipairs((seed.map or {}).patches or {}) do
    local origin = patch.kind == "item" and "en carte, mine" or "en carte, pumpjack"
    table.insert(lines, string.format(
      "  [PATCH] %s (%s, richesse=%s)",
      patch.resource,
      origin,
      patch.richness
    ))
  end
  return table.concat(lines, "\n")
end

local function get_character(player)
  if player.character and player.character.valid then
    return player.character
  end
  return nil
end

-- Convertit le starter_kit (liste d'entrées {name=,count=}) en dict
-- {name = count} attendu par les remote calls du freeplay.
local function starter_kit_map()
  local items = {}
  for _, entry in ipairs(seed.starter_kit or {}) do
    if entry and entry.name then
      items[entry.name] = (items[entry.name] or 0) + (entry.count or 1)
    end
  end
  return items
end

-- Configure le kit de départ / respawn du scenario freeplay pour qu'il pose
-- notre kit seed. Sans effet si le freeplay (ou ses remote calls) n'est pas
-- présent.
local function configure_freeplay_kit()
  if not remote.interfaces["freeplay"] then
    return
  end
  local ok, err = pcall(function()
    remote.call("freeplay", "set_created_items", starter_kit_map())
    remote.call("freeplay", "set_respawn_items", starter_kit_map())
  end)
  if ok then
    log("[randputF] kit freeplay configuré")
  else
    log("[randputF] échec configuration kit freeplay: " .. tostring(err))
  end
end

local function clear_spawn_inventory(player)
  local inv = player.get_main_inventory()
  if inv then
    inv.clear()
  end
  local character = get_character(player)
  if character then
    local gun_inv = character.get_inventory(defines.inventory.character_guns)
    if gun_inv then
      gun_inv.clear()
    end
    -- Le slot de balles de l'arme : character_ammo (PAS character_ammo_inventory
    -- qui n'existe pas en 2.0.77). On le vide sinon les munitions vanilla du
    -- pistol restent collées et bloquent le slot.
    local ammo_inv = character.get_inventory(defines.inventory.character_ammo)
    if ammo_inv then
      ammo_inv.clear()
    end
  end
end

local function init_storage()
  storage.randputf = storage.randputf or {}
  storage.randputf.seed = seed
  init_wreck()
end

-- ____________________________________________________________________________
-- Purge de l'eau vanilla §7.6
--
-- Le fix API (`autoplace probability_expression` + `property_expression_names`)
-- n'agit que sur les chunks GENERES APRES son activation. Une carte créée avant
-- garde définitivement ses tuiles water/deepwater (données en briques dans la
-- save). Ce balayage runtime les remplace par la terre dominante du chunk :
-- les cartes ANCIENNES sont réparées au premier chargement (mesuré : 139546
-- tuiles water/deepwater → 0 en ~1000 ticks), idempotent (les tuiles déjà
-- converties ne sont plus dans WATER_TILES). Nos lacs randputf sont exclus de
-- la liste : jamais nettoyés.
local WATER_PURGE_CHUNKS_PER_TICK = 32

-- Tuiles d'eau vanilla : mêmes noms que la liste neutralisée au mapgen
-- (data-updates.lua §7.5). Les lacs randputf-lac-* en sont évidemment exclus.
local WATER_TILES = {
  water = true, deepwater = true, ["water-shallow"] = true,
  ["water-green"] = true, ["deepwater-green"] = true, ["water-mud"] = true,
  ["water-wube"] = true,
}

local function purge_chunk_water(surface, cx, cy)
  local px, py = cx * 32, cy * 32
  local water_pos = {}
  local counts = {}
  for dy = 0, 31 do
    for dx = 0, 31 do
      local tile = surface.get_tile(px + dx, py + dy)
      if WATER_TILES[tile.name] then
        water_pos[#water_pos + 1] = { px + dx, py + dy }
      else
        counts[tile.name] = (counts[tile.name] or 0) + 1
      end
    end
  end
  if #water_pos == 0 then
    return
  end
  local best_name, best_count = "grass-1", 0
  for name, c in pairs(counts) do
    if c > best_count then
      best_name, best_count = name, c
    end
  end
  local tiles = {}
  for i = 1, #water_pos do
    tiles[i] = { position = water_pos[i], name = best_name }
  end
  surface.set_tiles(tiles, false)
end

-- Filet de sécurité en cas de spawn imparfait : fenêtre courte pendant laquelle
-- on vérifie que l'inventaire == kit seed exact et, sinon, on re-vide + re-dépose.
local SPAWN_SETTLE_TICKS = 120
local ARMED = {}  -- player_index -> ticks_left

local function set_armed(player_index)
  ARMED[player_index] = SPAWN_SETTLE_TICKS
end

-- Vrai si l'inventaire du joueur correspond EXACTEMENT au kit seed ET avec la
-- bonne répartition : chaque item de prototype "gun" doit se trouver dans les
-- slots d'arme du personnage (arme EN MAIN), chaque "ammo" dans le slot de
-- balles, et le reste (machines/plaques) dans l'inventaire principal. Aucun
-- item supplémentaire (doublon ou vanilla) n'est toléré.
--
-- Le scenario freeplay pose son kit via `insert_safe`, qui met TOUT à plat
-- dans l'inventaire principal (l'arme n'est alors pas en main) : cette fonction
-- retourne false dans ce cas, ce qui déclenche la purge pour re-normaliser la
-- répartition (clear + give).
local function kit_correct(player)
  local character = get_character(player)
  if not character then
    return false
  end
  local gun_inv = character.get_inventory(defines.inventory.character_guns)
  local ammo_inv = character.get_inventory(defines.inventory.character_ammo)
  local main_inv = player.get_main_inventory()
  if not (gun_inv and ammo_inv) then
    return false
  end

  local expected = {}
  for _, e in ipairs(seed.starter_kit or {}) do
    if e.name then
      expected[e.name] = (expected[e.name] or 0) + (e.count or 1)
    end
  end

  -- Compte les items dans chacun des trois emplacements (avec noms d'emplacements).
  local summary = {
    guns = {}, ammo = {}, main = {},
  }
  local function add_at(dst, inv)
    for i = 1, #inv do
      local s = inv[i]
      if s.valid_for_read then
        dst[s.name] = (dst[s.name] or 0) + s.count
      end
    end
  end
  add_at(summary.guns, gun_inv)
  add_at(summary.ammo, ammo_inv)
  add_at(summary.main, main_inv)

  -- Chaque item seed doit être au bon endroit, en quantité exacte.
  for name, want in pairs(expected) do
    local proto = name and prototypes.item[name]
    local ptype = proto and proto.type or "?"
    local bucket
    if ptype == "gun" then
      bucket = summary.guns
    elseif ptype == "ammo" then
      bucket = summary.ammo
    else
      bucket = summary.main
    end
    if (bucket[name] or 0) ~= want then
      return false
    end
  end

  -- Aucun autre item ne doit traîner (doublon ou vanilla résiduel).
  for _, bucket in pairs(summary) do
    for name in pairs(bucket) do
      if not expected[name] then
        return false
      end
    end
  end
  return true
end

local function give_starter_kit(player)
  local character = get_character(player)
  if not character then
    return false
  end
  local gun_inv = character.get_inventory(defines.inventory.character_guns)
  local ammo_inv = character.get_inventory(defines.inventory.character_ammo)
  for _, entry in ipairs(seed.starter_kit or {}) do
    local proto = entry.name and prototypes.item[entry.name]
    local ptype = proto and proto.type or "?"
    local leftover
    if ptype == "gun" and gun_inv then
      leftover = gun_inv.insert({name = entry.name, count = entry.count})
      if leftover > 0 then
        player.insert({name = entry.name, count = leftover})
      end
    elseif ptype == "ammo" and ammo_inv then
      leftover = ammo_inv.insert({name = entry.name, count = entry.count})
      if leftover > 0 then
        player.insert({name = entry.name, count = leftover})
      end
    else
      leftover = player.insert({name = entry.name, count = entry.count})
    end
  end
  return true
end

local function apply_spawn_kit(player)
  if not get_character(player) then
    return false
  end
  clear_spawn_inventory(player)
  give_starter_kit(player)
  return true
end

-- ____________________________________________________________________________
-- Handlers

script.on_configuration_changed(function()
  configure_freeplay_kit()
end)

script.on_init(function()
  init_storage()
  configure_freeplay_kit()

  local force = game.forces.player
  for _, tech_name in ipairs(seed.free_researches or {}) do
    local tech = force.technologies[tech_name]
    if tech then
      tech.researched = true
      local ok, effects = pcall(function() return tech.effects end)
      if ok and effects then
        for _, effect in ipairs(effects) do
          if effect.type == "unlock-recipe" then
            if force.recipes[effect.recipe] then
              force.recipes[effect.recipe].enabled = true
            end
          end
        end
      end
    end
  end

  -- Les conteneurs du crash sont créés par le scénario au boot : le balayage
  -- par on_tick (fenêtre WRECK_SETTLE_TICKS) les ratisse après coup, une fois
  -- chacun (protection unit_number), pour vider + remplir aléatoirement (§7).
  for _, surface in pairs(game.surfaces) do
    process_crash_site(surface)
  end

  -- Diagnostic des lacs (§7.5) : les tuiles `randputf-lac-<fluid>` sont posées
  -- par autoplace (data stage) ; on compte celles du voisinage du spawn.
  local nauvis = game.surfaces[1]
  if nauvis then
    for _, lake in ipairs((seed.map or {}).lakes or {}) do
      local tiles = nauvis.find_tiles_filtered{
        area = {{-320, -320}, {320, 320}},
        name = "randputf-lac-" .. lake.resource,
      }
      log(string.format(
        "[randputF] lac: %s -> %d tuiles à proximité du spawn",
        lake.resource,
        #tiles
      ))
    end
  end
end)

script.on_load(function()
  -- On ne peut PAS toucher `game` ni muter `storage` ici (API 2.0) : on
  -- restaure juste le storage des composants runtime qui en dépendent
  -- (références + loi du site de crash). Les éventuels filets de sécurité
  -- d'équipement sont réarmés par on_player_joined / on_tick.
end)

script.on_event(defines.events.on_player_created, function(event)
  local player = game.get_player(event.player_index)
  if not player then
    return
  end
  player.print(describe_patches())
  -- Le freeplay a déjà posé notre kit (configuré via set_created_items) ; on
  -- installe juste le filet de sécurité au cas où l'état ne correspondrait pas.
  set_armed(event.player_index)
end)

script.on_event(defines.events.on_player_respawned, function(event)
  -- Après un respawn, le freeplay re-pose notre kit (`respawn_items`) mais à
  -- plat dans l'inventaire principal : on normalise la répartition (arme en
  -- main, munitions au slot de balles).
  set_armed(event.player_index)
end)

script.on_event(defines.events.on_player_joined_game, function(event)
  -- Reconnect après chargement de sauvegarde : réarme le filet de sécurité
  -- (le ARMED global ne survit pas au reload).
  set_armed(event.player_index)
end)

script.on_event(defines.events.on_tick, function()
  for idx, ticks_left in pairs(ARMED) do
    if ticks_left <= 0 then
      ARMED[idx] = nil
    else
      ARMED[idx] = ticks_left - 1
      local p = game.get_player(idx)
      if p and p.valid and p.character and p.character.valid then
        if not kit_correct(p) then
          apply_spawn_kit(p)
        end
      end
    end
  end

  -- Purge de l'eau vanilla (§7.6) : les cartes générées AVANT le fix
  -- property_expression_names gardent leurs tuiles water/deepwater sur les
  -- chunks déjà créés. Balayage incrémental de chunks générés (32 par tick) en
  -- carré croissant jusqu'à épuisement de la zone explorée. Le curseur est
  -- persisté (storage.water_purge) donc la passe reprend après rechargement,
  -- et elle est idempotente (les tuiles converties ne sont plus dans la liste).
  local purge = storage.randputf.water_purge
  local done = false
  if purge ~= nil then
    local surface = game.surfaces[1]
    if purge.ring ~= nil then
      local R = purge.ring
      local x, y = purge.x, purge.y
      for k = 1, WATER_PURGE_CHUNKS_PER_TICK do
        while true do
          if y > R then
            y = -R
            R = R + 1
            if math.abs(R) > 256 then
              done = true
              break
            end
          end
          if surface.is_chunk_generated({x, y}) then
            purge_chunk_water(surface, x, y)
          end
          x = x + 1
          if x > R then
            x = -R
            y = y + 1
          end
          break
        end
        if done then break end
      end
      if done then
        storage.randputf.water_purge = nil
        storage.randputf.water_purge_done = true
      else
        purge.x, purge.y, purge.ring = x, y, R
      end
    end
  else
    -- Pas encore lancée : on amorce UNE passe sur la surface principale. La
    -- marque water_purge_done évite de rescanner sans cesse les maps neuves.
    if storage.randputf.water_purge_done == nil and game.surfaces[1] then
      storage.randputf.water_purge = { ring = 0, x = 0, y = 0 }
    end
  end

  -- Balayage du site de crash : pendant la fenêtre de démarrage, on ratisse
  -- régulièrement les surfaces pour traiter les conteneurs du crash créés par
  -- le scénario APRES notre on_init (l'idempotence est garantie par la marque
  -- unit_number : chaque conteneur n'est rempli qu'une seule fois).
  local stop = storage.randputf.wreck_stop
  if stop ~= nil then
    if game.tick > stop then
      storage.randputf.wreck_stop = nil
    elseif game.tick % WRECK_SWEEP_INTERVAL == 0 then
      for _, surface in pairs(game.surfaces) do
        process_crash_site(surface)
      end
    end
  end
end)

script.on_event(defines.events.on_surface_created, function(event)
  local surface = game.get_surface(event.surface_index)
  if surface then
    process_crash_site(surface)
  end
end)

script.on_event(defines.events.on_chunk_generated, function(event)
  local surface = event.surface
  if surface and surface.valid then
    process_crash_site(surface, event.area)
  end
end)
