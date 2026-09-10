-- randputF — contrôle runtime.
--
-- Stratégie de spawn : le kit est délivré 100% par nous, PAS par le freeplay.
-- On NEUTRALISE le kit du scenario freeplay (created_items + respawn_items à
-- vide via les remote calls) puis on distribue nous-mêmes :
--   * on_player_created  → le kit seed COMPLET (arme + munitions + machines),
--     une seule fois par vie ;
--   * on_player_respawned → un kit de survie MINCE (pistol + munitions),
--     jamais le kit complet (une mort ne re-stocke pas le kit de départ) ;
--   * jamais au chargement d'une sauvegarde (on_player_joined) : réarmer là
--     viderait l'inventaire du joueur en cours de partie.
-- Un filet court (fenêtre SPAWN_SETTLE_TICKS, garde KIT_APPLIED par vie)
-- rattrape le cas où le personnage n'existe pas encore à on_player_created
-- (cutscene du crash) : il applique le kit UNE fois dès que le personnage est
-- là. Le scénario crash-site insère parfois ses propres items (SMG + munitions)
-- en différé ou dans d'autres slots d'armes (2.0) : un normaliseur (points de
-- contrôle 300/900/1800 ticks, §7) ramène le kit à son EXACT contenu à la volée,
-- sans jamais toucher le loot du joueur. Aucun autre chemin ne fournit d'items
-- de spawn.
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
-- Garantie : un conteneur n'est JAMAIS entièrement vide (force-fill si 0 stack).
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
  local filled = 0
  for i = 1, #inv do
    local n = draw_slot_count(counts, rng)
    if n > 0 and #loot > 0 then
      local mat = loot[rng(1, #loot)]
      if mat and not inv[i].valid_for_read then
        inv[i].set_stack({name = mat, count = n})
        filled = filled + 1
      end
    end
  end
  -- Garantie : un conteneur du crash n'est JAMAIS entièrement vide (sinon le
  -- joueur perçoit « le vaisseau est vide »). Si le tirage pondéré a tout mis
  -- à 0 (possible), on force 1 matériau dans le premier slot.
  if filled == 0 and #inv > 0 and #loot > 0 then
    inv[1].set_stack({name = loot[rng(1, #loot)], count = 1})
    filled = 1
  end
  if unit then
    storage.randputf.wreck_processed[unit] = true
  end
  log(string.format(
    "[randputF] wreck: %s rempli (%d stacks sur %d slots, loi %s)",
    entity.name,
    filled,
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
--   [PATCH] = gisement posé au RUNTIME par le mod (§6.5) — puits (pumpjack)
--            pour un fluide, blocs (foreuse) pour un item.
-- Chaque nom est affiché avec son ICONE (texte enrichi : `[item=...]` pour un
-- item, `[fluid=...]` pour un fluide) : le nom seul ne suffit pas pour les
-- pétroles (petroleum-gas, light-oil, ...) qui se ressemblent à l'écran.
local function resource_label(kind, resource)
  local tag = (kind == "item") and "item" or "fluid"
  return "[" .. tag .. "=" .. resource .. "]"
end

local function describe_patches()
  local lines = {}
  table.insert(lines, "[randputF] RESSOURCES DE LA SEED #" .. tostring(seed.meta and seed.meta.seed or "?"))
  for _, lake in ipairs((seed.map or {}).lakes or {}) do
    table.insert(lines, string.format(
      "  [LAC] %s (infini, richesse=%s)",
      resource_label("fluid", lake.resource),
      lake.richness
    ))
  end
  for _, patch in ipairs((seed.map or {}).patches or {}) do
    local origin
    if patch.kind == "item" then
      origin = "gisement " .. tostring(patch.count or 0) .. " blocs"
    else
      origin = "puits oil " .. tostring(patch.count or 0) .. " puits"
    end
    local extra = ", centre=" .. tostring((patch.center or {}).x) .. ","
      .. tostring((patch.center or {}).y)
    table.insert(lines, string.format(
      "  [PATCH] %s (%s, richesse=%s%s)",
      resource_label(patch.kind, patch.resource),
      origin,
      patch.richness,
      extra
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

-- Neutralise le kit de départ / respawn du scenario freeplay : created_items +
-- respawn_items à VIDE, la délivrance est 100% chez nous (on_player_created /
-- on_player_respawned). Sans effet si le freeplay (ou ses remote calls) n'est
-- pas présent.
local function configure_freeplay_kit()
  if not remote.interfaces["freeplay"] then
    return
  end
  local ok, err = pcall(function()
    remote.call("freeplay", "set_created_items", {})
    remote.call("freeplay", "set_respawn_items", {})
  end)
  if ok then
    log("[randputF] kit freeplay neutralisé (délivrance hors freeplay)")
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
-- Purge de l'eau vanilla §7.5
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

-- Filet de sécurité en cas de spawn différé (cutscene du crash) : fenêtre
-- courte pendant laquelle on applique le kit UNE fois dès que le personnage
-- existe. La garde KIT_APPLIED (par vie, nil au spawn) garantit qu'on ne le
-- re-dépose JAMAIS deux fois : aucune course freeplay/mod ne peut donner deux
-- kits.
local SPAWN_SETTLE_TICKS = 1200
local ARMED = {}       -- player_index -> ticks_left
local KIT_APPLIED = {} -- player_index -> true (kit complet déjà posé cette vie)

local function set_armed(player_index)
  ARMED[player_index] = SPAWN_SETTLE_TICKS
end

-- ____________________________________________________________________________
-- Enforcement (§7) : le scénario crash-site insère ses propres items (dont le
-- SMG + munitions) dans l'inventaire du personnage, parfois APRES
-- on_player_created (cutscene) ou dans des slots différents (2.0 : plusieurs
-- slots d'armes, ammo par slot). On neutralise donc tout surplus PAR RAPPORT au
-- kit seed à plusieurs points de contrôle. Jamais de clear global : on ne touche
-- que les items de notre plan (le loot du joueur est préservé).
local KIT_ENFORCE_TICKS = { 300, 900, 1800 } -- points de contrôle (tick)
local KIT_ENFORCE = {} -- player_index -> index du prochain point de contrôle

-- Plan du kit seed : nom -> { count, type }. Calculé une fois.
local KIT_PLAN = nil
local function kit_plan()
  if KIT_PLAN then
    return KIT_PLAN
  end
  KIT_PLAN = {}
  for _, entry in ipairs(seed.starter_kit or {}) do
    local proto = entry.name and prototypes.item[entry.name] or {}
    local ptype = proto.type or "?"
    local p = KIT_PLAN[entry.name]
    if not p then
      p = { count = 0, type = ptype }
      KIT_PLAN[entry.name] = p
    end
    p.count = p.count + entry.count
  end
  return KIT_PLAN
end

-- DIAG : journalise les compteurs des items du kit pour tracer les doublons.
local function log_kit_state(label, player)
  local parts = {}
  for _, entry in ipairs(seed.starter_kit or {}) do
    local c = player.get_item_count(entry.name)
    if c > 0 then parts[#parts + 1] = entry.name .. "=" .. c end
  end
  local p = player.get_item_count("pistol")
  if p > 0 then parts[#parts + 1] = "pistol=" .. p end
  local fm = player.get_item_count("firearm-magazine")
  if fm > 0 then parts[#parts + 1] = "firearm-magazine=" .. fm end
  table.sort(parts)
  log("[randputF][KIT] " .. label .. " {" .. table.concat(parts, ", ") .. "}")
end

-- DIAG dure : dump de CHAQUE slot des inventaires du personnage (voir dans
-- quel inventaire vit le doublon : main / gun slots / ammo slots).
local function dump_character_inventories(player, label)
  local character = get_character(player)
  if not character then
    log("[randputF][KIT] " .. label .. ": aucun personnage")
    return
  end
  local main_inv = player.get_main_inventory()
  if main_inv then
    local parts = {}
    for i = 1, #main_inv do
      local s = main_inv[i]
      if s and s.valid_for_read then
        parts[#parts + 1] = i .. ":" .. s.name .. "x" .. s.count
      end
    end
    log("[randputF][KIT] " .. label .. " main [" .. table.concat(parts, ", ") .. "]")
  end
  for _, spec in ipairs{
    { name = "guns", inv = character.get_inventory(defines.inventory.character_guns) },
    { name = "ammo", inv = character.get_inventory(defines.inventory.character_ammo) },
  } do
    local parts = {}
    if spec.inv then
      for i = 1, #spec.inv do
        local s = spec.inv[i]
        if s and s.valid_for_read then
          parts[#parts + 1] = i .. ":" .. s.name .. "x" .. s.count
        end
      end
    end
    log("[randputF][KIT] " .. label .. " " .. spec.name .. " [" .. table.concat(parts, ", ") .. "]")
  end
end

-- Kit seed : dépôt exact des items du kit (guns/munitions dans les bons
-- inventaires, le reste dans l'inventaire principal). Idempotent.
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

-- Normaliseur : ramène chaque item du plan seed à sa quantité cible, où qu'il
-- vive. Gun/ammo hors de leur slot (ex. SMG dans le main) = doublon du
-- scénario → retiré. Excédent dans le slot cible → retiré depuis la fin. Item
-- machine manquant (ex. steel-furnace) → ré-inséré. Chirurgical : aucun autre
-- item n'est touché.
local function normalize_kit(player)
  local character = get_character(player)
  if not character then
    return
  end
  local plan = kit_plan()
  local gun_inv = character.get_inventory(defines.inventory.character_guns)
  local ammo_inv = character.get_inventory(defines.inventory.character_ammo)
  local main_inv = player.get_main_inventory()

  -- 1) Gun/ammo hors de leur slot cible : retirés de l'inventaire principal.
  for name, spec in pairs(plan) do
    if spec.type == "gun" or spec.type == "ammo" then
      if main_inv then
        -- Retire TOUTES les copies de ce gun/ammo du main (elles doivent vivre
        -- dans leur slot). Compter la quantité d'abord : `remove` n'accepte pas
        -- math.huge (= inf) comme count.
        local amount = 0
        for i = 1, #main_inv do
          local s = main_inv[i]
          if s and s.valid_for_read and s.name == name then
            amount = amount + s.count
          end
        end
        if amount > 0 then
          main_inv.remove{ name = name, count = amount }
        end
      end
      -- 2) Excédent dans le slot cible : retiré depuis la fin du slot.
      local slot_inv = (spec.type == "gun" and gun_inv) or (spec.type == "ammo" and ammo_inv)
      local cur = player.get_item_count(name)
      local excess = cur - spec.count
      if excess > 0 and slot_inv then
        for i = #slot_inv, 1, -1 do
          if excess <= 0 then
            break
          end
          local s = slot_inv[i]
          if s and s.valid_for_read then
            local take = math.min(excess, s.count)
            -- Retirer TOUTE la stack (take == s.count) ⇒ count = 0 refusé par
            -- l'API (« count must be positive ») : on vide la stack au lieu
            -- de faire un set_stack{count = 0}.
            if s.count - take > 0 then
              s.set_stack{ name = s.name, count = s.count - take }
            else
              s.clear()
            end
            excess = excess - take
          end
        end
      end
      -- 3) Déficit (ex. notre arme restée dans le main après un clear du
      -- scénario) : ré-équipée dans le slot cible.
      local cur2 = player.get_item_count(name)
      if cur2 < spec.count then
        local need = spec.count - cur2
        local leftover = need
        if slot_inv then
          leftover = slot_inv.insert{ name = name, count = need }
        end
        if leftover > 0 then
          player.insert{ name = name, count = leftover }
        end
      end
    end
  end

  -- 4) Items machine du plan manquants : ré-insérés.
  for name, spec in pairs(plan) do
    local cur = player.get_item_count(name)
    if cur < spec.count and spec.type ~= "gun" and spec.type ~= "ammo" then
      player.insert{ name = name, count = spec.count - cur }
    end
  end
end

-- Kit seed COMPLET au premier spawn : purge + dépôt. C'est le SEUL chemin qui
-- distribue le kit complet (pas le freeplay, pas un rechargement de partie).
local function apply_spawn_kit(player)
  if not get_character(player) then
    return false
  end
  clear_spawn_inventory(player)
  give_starter_kit(player)
  return true
end

-- Kit de respawn volontairement MINCE (une arme + des munitions), jamais le
-- kit complet : une mort ne re-stocke pas le kit de départ au complet — c'était
-- la cause perçue du « 2 fois le starter pack » (mort au site de crash → kit
-- complet re-donné). Miroir du respawn vanilla (pistol + 10 firearm-magazine).
local RESPAWN_KIT = {
  { name = "pistol", count = 1 },
  { name = "firearm-magazine", count = 10 },
}

local function give_respawn_kit(player)
  local character = get_character(player)
  if not character then
    return false
  end
  local gun_inv = character.get_inventory(defines.inventory.character_guns)
  local ammo_inv = character.get_inventory(defines.inventory.character_ammo)
  for _, entry in ipairs(RESPAWN_KIT) do
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
      player.insert({name = entry.name, count = entry.count})
    end
  end
  return true
end

local function apply_respawn_kit(player)
  if not get_character(player) then
    return false
  end
  clear_spawn_inventory(player)
  give_respawn_kit(player)
  return true
end

-- ____________________________________________________________________________
-- §7.5 — REMPLISSAGE DES LACS PAR FLOOD-FILL
--
-- Les lacs sont DESSINÉS par le moteur d'altitude natif de Factorio : toute
-- l'eau devient la tuile « fantôme » randputf-lac-neutre (fluide inexistant —
-- voire les définitions data-updates.lua). Au runtime on les REMPLIT : quand
-- un chunk est généré, chaque tuile fantôme entreprise une flood-fill (BFS)
-- de tout le lac connexe contenu dans le chunk, et toutes ses tuiles sont
-- remplacées par la tuile-par-fluide choisie. La sélection :
--   * si une tuile VOISINE (dans le chunk OU d'un chunk déjà généré) est déjà
--     une tuile-par-fluide → le lac ADOPTE ce fluide (propagation le long du
--     lac, y compris à travers les limites de chunks : un même lac n'a jamais
--     deux fluides) ;
--   * sinon (lac « frais », sans voisin coloré) → on tire le PROCHAIN fluide
--     de la seed, en boucle (tourniquet) : chaque lac indépendant reçoit un
--     fluide, et s'il y a plus de lacs que de fluides on réutilise en boucle.
-- Une tuile transformée n'est plus fantôme, donc jamais re-traversée : c'est
-- le « visited » naturel — on ne repasse jamais deux fois sur le même lac.
local PHANTOM_TILE = "randputf-lac-neutre"

-- Tuiles-par-fluide dans l'ordre de la seed ; lookup nom de tuile -> fluide.
local LAKE_FLUID_TILES = {}
local LAKE_FLUID_LOOKUP = {}

local function init_lake_fluids()
  LAKE_FLUID_TILES = {}
  LAKE_FLUID_LOOKUP = {}
  local lakes = (seed.map or {}).lakes or {}
  for _, lk in ipairs(lakes) do
    local tile = "randputf-lac-" .. lk.resource
    LAKE_FLUID_TILES[#LAKE_FLUID_TILES + 1] = lk.resource
    LAKE_FLUID_LOOKUP[tile] = lk.resource
  end
end

-- Prochain fluide de la seed, en boucle (persisté dans storage pour rester
-- stable entre chunks/sessions). N'est appelé que pour un lac FRAIS.
local function next_lake_fluid_tile()
  local n = #LAKE_FLUID_TILES
  if n == 0 then return nil end
  local idx = storage.randputf.lake_index or 0
  idx = idx % n + 1
  storage.randputf.lake_index = idx
  return LAKE_FLUID_TILES[idx]
end

-- Flood-fill d'un lac connexe contenu dans `area` (un chunk) à partir de la
-- tuile fantôme (x0,y0). Retourne la liste des positions fantômes du lac.
local function flood_fill_phantom(surface, x0, y0, area)
  local minx, maxx = area.left_top.x, area.right_bottom.x - 1
  local miny, maxy = area.left_top.y, area.right_bottom.y - 1
  local region = {}
  local seen = {}
  local queue = { {x0, y0} }
  seen[x0 .. "," .. y0] = true
  local head = 1
  while head <= #queue do
    local p = queue[head]
    head = head + 1
    local px, py = p[1], p[2]
    local tile = surface.get_tile(px, py)
    if tile.valid and tile.name == PHANTOM_TILE then
      region[#region + 1] = { px, py }
      local dirs = { {1, 0}, {-1, 0}, {0, 1}, {0, -1} }
      for _, d in ipairs(dirs) do
        local nx, ny = px + d[1], py + d[2]
        if nx >= minx and nx <= maxx and ny >= miny and ny <= maxy then
          local key = nx .. "," .. ny
          if not seen[key] then
            seen[key] = true
            queue[#queue + 1] = { nx, ny }
          end
        end
      end
    end
  end
  return region
end

-- Détermine le fluide d'un lac frais : réutilise le fluide d'un voisin déjà
-- coloré (propagation inter-chunks), sinon retourne nil.
local function neighbor_lake_fluid(surface, region)
  local dirs = { {1, 0}, {-1, 0}, {0, 1}, {0, -1} }
  for _, p in ipairs(region) do
    for _, d in ipairs(dirs) do
      local t = surface.get_tile(p[1] + d[1], p[2] + d[2])
      if t.valid then
        local fluid = LAKE_FLUID_LOOKUP[t.name]
        if fluid then
          return fluid
        end
      end
    end
  end
  return nil
end

-- Remplit un lac connexe dans `area` en partant d'une tuile fantôme (x0,y0).
local function fill_lake(surface, x0, y0, area)
  local region = flood_fill_phantom(surface, x0, y0, area)
  if #region == 0 then return end
  local fluid = neighbor_lake_fluid(surface, region) or next_lake_fluid_tile()
  if not fluid then
    return
  end
  local tile_name = "randputf-lac-" .. fluid
  local tiles = {}
  for i, p in ipairs(region) do
    tiles[i] = { position = p, name = tile_name }
  end
  -- correct_tiles = true (défaut) : le remplacement tuile-fantôme -> tuile-lac
  -- recalcule les bords autour des tuiles modifiées. Les tuiles-lac étant déjà
  -- ciblées par les transitions des tuiles de terre (data-updates §7.5), les
  -- berges sable/herbe du biome se dessinent autour du lac rempli.
  surface.set_tiles(tiles)
end

-- Balaye le chunk généré : chaque tuile fantôme non encore remplie démarre un
-- fill_lake sur tout son lac connexe. (Appelé depuis on_chunk_generated.)
local function fill_lakes_in_area(surface, area)
  if #LAKE_FLUID_TILES == 0 then return end
  local minx, maxx = area.left_top.x, area.right_bottom.x - 1
  local miny, maxy = area.left_top.y, area.right_bottom.y - 1
  for y = miny, maxy do
    for x = minx, maxx do
      local tile = surface.get_tile(x, y)
      if tile.valid and tile.name == PHANTOM_TILE then
        fill_lake(surface, x, y, area)
      end
    end
  end
end

-- ── Gisements posés au runtime (§6.5) ──────────────────────────────────────
-- Les patchs (ITEMS et FLUIDES) ne sont plus placés par le mapgen (autoplace à
-- base_density=0 dans data-updates). Ici, à chaque chunk généré, on pose les
-- blocs/puits du gisement sur ce chunk : entité-resource
-- `randputf-minerai-<item>` (minée par une foreuse) ou `randputf-oil-<fluide>`
-- (pompée par un pumpjack). La position de chaque bloc est dérivée de façon
-- REPRODUCTIBLE et INDÉPENDANTE de l'ordre de génération des chunks : on crée
-- un PRNG frais par bloc (seed = well_seed + index), donc l'ordre
-- chunk-par-chunk n'importe pas. Richesse = celle de la seed, appliquée au
-- runtime via entity.amount.
local WELL_MIX = 2654435761 -- constant de mélange (Knuth), masqué sous 2^31

local function place_resource_block(surface, entity_name, x, y, richness)
  local pos = { x, y }
  if not surface.can_place_entity{ name = entity_name, position = pos, forced = true } then
    return false
  end
  local e = surface.create_entity{ name = entity_name, position = pos }
  if not (e and e.valid) then
    return false
  end
  if richness and richness > 0 then
    e.amount = richness
    -- `initial_amount` est INSCRIPTIBLE sur les gisements INFINIS uniquement
    -- (API 1.1+) : aucune propriété prototype ne l'expose au runtime, on le
    -- tente donc en pcall — un gisement FINI jette silencieusement
    -- « Can't set initial amount on a non-infinite resource entity » et la
    -- richesse reste posée via `amount`.
    pcall(function() e.initial_amount = richness end)
  end
  return true
end

-- Positions des blocs/puits du gisement `patch` qui tombent dans l'aire `area`.
--
-- ITEM : le champ est produit AVEC L'ALGO DU MAPGEN VANILLA — une tuile est
-- posée ssi un champ de BRUIT LISSE seuillé y dépasse un seuil (l'équivalent
-- de `ore iff noise(tile) >= 0` de resource_autoplace). Le bruit lisse
-- (interpolation bilinéaire value-noise) rend les veines ORGANIQUES :
-- contours sinueux, avancées/dents, trous internes — jamais des cercles
-- parfaits. Déterministe : graine = well_seed, dérivée de coordonnées de
-- tuile uniquement (indépendant de l'ordre des chunks). `count` (= aire du
-- disque nominale) ne sert qu'à répartir la richesse par tuile.
local NOISE_CELL = 4      -- maille du bruit (échelle du relief des veines)
local NOISE_WOBBLE = 0.20 -- amplitude du bruit sur le bord (contours sinueux)
local NOISE_SHAKE = 127.1

local function vnoise(seed, x, y)
  local s = math.sin(x * NOISE_SHAKE + y * 311.7 + seed) * 43758.5453123
  return s - math.floor(s)
end

local function smooth_noise(seed, x, y)
  local x0 = math.floor(x / NOISE_CELL)
  local y0 = math.floor(y / NOISE_CELL)
  local fx = x / NOISE_CELL - x0
  local fy = y / NOISE_CELL - y0
  local ux = fx * fx * (3 - 2 * fx)
  local uy = fy * fy * (3 - 2 * fy)
  local a = vnoise(seed, x0, y0)
  local b = vnoise(seed, x0 + 1, y0)
  local c = vnoise(seed, x0, y0 + 1)
  local d = vnoise(seed, x0 + 1, y0 + 1)
  return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy
end

local function block_positions_in_area(patch, area)
  local out = {}
  local center = patch.center or {}
  local cx, cy = center.x or 0, center.y or 0
  local radius = patch.cluster_radius or 10
  local count = patch.count or 0
  local well_seed = patch.well_seed or 0
  local minx, maxx = area.left_top.x, area.right_bottom.x - 1
  local miny, maxy = area.left_top.y, area.right_bottom.y - 1
  if patch.kind == "fluid" then
    -- Puits FLUIDES éparpillés à l'extérieur du centre (0.25..1) : la densité
    -- n'apporte rien à un pumpjack, il se branche sur n'importe quelle tuile.
    for idx = 0, count - 1 do
      local g = game.create_random_generator((well_seed + idx * WELL_MIX) % 2147483648)
      local ang = g() * 2 * math.pi
      local rd = radius * (0.25 + g() * 0.75)
      local wx = math.floor(cx + 0.5 + math.cos(ang) * rd)
      local wy = math.floor(cy + 0.5 + math.sin(ang) * rd)
      if wx >= minx and wx <= maxx and wy >= miny and wy <= maxy then
        out[#out + 1] = { wx, wy }
      end
    end
  else
    -- Champ ITEM organique type vanilla (thresholded noise). Deux bruits
    -- lisses : le 1er fait onduler le bord (dents/avancées), le 2nd règle la
    -- densité (cœur plein, bords qui se délitent + trous internes).
    local seed_a = well_seed
    -- Constante Φ (partie entière, ~1.6e9) pour décorréler le 2e champ de
    -- bruit (addition exacte sans dépassement flottant).
    local seed_b = well_seed + 1618033989
    local margin = math.ceil(radius * (1 + NOISE_WOBBLE))
    local first_wy = math.max(miny, cy - margin)
    local last_wy = math.min(maxy, cy + margin)
    local first_wx = math.max(minx, cx - margin)
    local last_wx = math.min(maxx, cx + margin)
    for wy = first_wy, last_wy do
      for wx = first_wx, last_wx do
        local dx = wx - cx
        local dy = wy - cy
        local d = math.sqrt(dx * dx + dy * dy)
        local wobble = (smooth_noise(seed_a, wx, wy) - 0.5) * 2 * radius * NOISE_WOBBLE
        if d <= radius + wobble then
          local edge = d / radius
          -- Densité « ore vanilla » : le CŒUR est quasi plein, le champ se
          -- délite en allant vers le bord (jamais l'inverse). Bruit comparé
          -- EN DESSOUS du seuil : seuil haut au centre (≈90 % gardé), seuil
          -- qui chute au bord (≈30 %) → gisement qui se dissout en poussière
          -- comme une vraie couche de minerai, sans « tout manger au milieu ».
          if smooth_noise(seed_b, wx, wy) < 0.90 - edge * 0.60 then
            out[#out + 1] = { wx, wy }
          end
        end
      end
    end
  end
  return out
end

-- Balaye `area` et pose les blocs/puits des patchs (item ET fluide) qui y
-- tombent. (Appelé depuis on_chunk_generated, APRÈS les lacs.) Un bloc qui
-- tomberait sur un lac (eau) ou un autre obstacle est simplement ignoré : la
-- position est un obstacle = on saute, le gisement garde ses autres blocs.
local function place_patch_gisements_in_area(surface, area)
  for _, patch in ipairs((seed.map or {}).patches or {}) do
    local entity_name
    if patch.kind == "fluid" then
      entity_name = "randputf-oil-" .. patch.resource
    else
      entity_name = "randputf-minerai-" .. patch.resource
    end
    -- FLUIDE : la richesse est un RENDEMENT par puits (chaque puits vaut
    -- `richness`). ITEM : la richesse est le TOTAL du champ — répartie par
    -- tuile (richness / count), comme une vraie couche d'ore vanilla qui se
    -- tarit morceau par morceau.
    local richness = patch.richness
    local per_tile = richness
    if patch.kind ~= "fluid" and patch.count and patch.count > 0 then
      per_tile = math.max(1, math.floor(richness / patch.count))
    end
    for _, pos in ipairs(block_positions_in_area(patch, area)) do
      place_resource_block(surface, entity_name, pos[1], pos[2], per_tile)
    end
  end
end

-- Calculé une fois au chargement du mod (re-calculé à chaque chargement de
-- session) : indépendant de game, donc fiable aussi en on_load.
init_lake_fluids()


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

  -- Lacs (§7.5) : remplissage fait dans on_chunk_generated (flood-fill), les
  -- fluides/positions sont déjà initialisés au module scope (init_lake_fluids).
  -- Le kit de spawn n'est PAS posé ici : il est délivré aux événements
  -- on_player_created / on_player_respawned (et jamais au rechargement).
end)

script.on_load(function()
  -- On ne peut PAS toucher `game` ni muter `storage` ici (API 2.0) : on
  -- restaure juste le storage des composants runtime qui en dépendent
  -- (références + loi du site de crash). Le kit de spawn n'est pas concerné :
  -- jamais redonné à on_player_joined (charge/reconnexion).
end)

script.on_event(defines.events.on_player_created, function(event)
  local idx = event.player_index
  local player = game.get_player(idx)
  if not player then
    return
  end
  player.print(describe_patches())
  -- Nouvelle vie : on autorise UN dépôt du kit complet (garde réarmée).
  KIT_APPLIED[idx] = nil
  -- Délivrance immédiate si le personnage existe déjà ; sinon le filet
  -- (fenêtre courte) l'appliquera une fois que le personnage sera là.
  if apply_spawn_kit(player) then
    KIT_APPLIED[idx] = true
  end
  log_kit_state("created", player)
  set_armed(idx)
  -- Enforcement : le scénario crash-site peut insérer des items en différé
  -- (cutscene) ou dans d'autres slots. Le normaliseur (points de contrôle 300 /
  -- 900 / 1800 ticks) ramène le kit à son exact contenu au fil du temps.
  KIT_ENFORCE[idx] = 1
end)

script.on_event(defines.events.on_player_respawned, function(event)
  local idx = event.player_index
  local player = game.get_player(idx)
  if not player then
    return
  end
  -- Si KIT_APPLIED n'est PAS encore vrai, c'est le spawn initial (pas une
  -- vraie mort). On ne touche à rien : le kit complet sera délivré par
  -- on_player_created / le filet. Si KIT_APPLIED est vrai, c'est une vraie
  -- mort → on pose le kit de survie mince (pistol + firearm×10).
  if not KIT_APPLIED[idx] then
    log("[randputF][KIT] respawn skipped (initial spawn, KIT_APPLIED=nil)")
    return
  end
  apply_respawn_kit(player)
  log_kit_state("respawn", player)
end)

-- NOTE : PAS de handler on_player_joined_game. Réarmer le filet au chargement
-- d'une sauvegarde (ou reconnexion) purgerait l'inventaire du joueur en cours
-- de partie (le kit ne correspond plus après quelques heures de jeu). Le kit
-- n'est distribué qu'à on_player_created / on_player_respawned.

script.on_event(defines.events.on_tick, function()
  for idx, ticks_left in pairs(ARMED) do
    if ticks_left <= 0 or KIT_APPLIED[idx] then
      ARMED[idx] = nil
    else
      ARMED[idx] = ticks_left - 1
      local p = game.get_player(idx)
      if p and p.valid and p.character and p.character.valid then
        if apply_spawn_kit(p) then
          KIT_APPLIED[idx] = true
          ARMED[idx] = nil
        end
      end
    end
  end

  -- Enforcement (§7) : normalise le kit aux points de contrôle définis, pour
  -- neutraliser les doublons injectés par le scénario (slots d'armes 2.0,
  -- insertions pendant la cutscene). Le dump d'inventaire n'a lieu qu'au 1er
  -- passage, pour identifier où vit le doublon.
  for idx, stage in pairs(KIT_ENFORCE) do
    local target = KIT_ENFORCE_TICKS[stage]
    if target and game.tick >= target then
      local p = game.get_player(idx)
      if p and p.valid and p.character and p.character.valid then
        if stage == 1 then
          dump_character_inventories(p, "settle1")
        end
        normalize_kit(p)
        log_kit_state("settle" .. stage, p)
        KIT_APPLIED[idx] = true
        log("[randputF][KIT] enforcement stage " .. stage .. " (tick=" .. game.tick .. ")")
      end
      stage = stage + 1
      if stage > #KIT_ENFORCE_TICKS then
        KIT_ENFORCE[idx] = nil
      else
        KIT_ENFORCE[idx] = stage
      end
    end
  end

  -- Purge de l'eau vanilla (§7.5) : les cartes générées AVANT le fix
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

  -- DIAG TEMPORAIRE (§7.5) : une fois, scanne une zone autour du spawn et
  -- journalise la composition des tuiles-lac (fantôme restantes vs fluides).
  if storage.randputf.__diag_lakes_done == nil and game.tick > 30 then
    storage.randputf.__diag_lakes_done = true
    local s = game.surfaces[1]
    if s then
      local counts = {}
      local phantom = 0
      for dy = -256, 256, 2 do
        for dx = -256, 256, 2 do
          local t = s.get_tile(dx, dy)
          if t and t.valid then
            if t.name == PHANTOM_TILE then
              phantom = phantom + 1
            elseif LAKE_FLUID_LOOKUP[t.name] then
              counts[t.name] = (counts[t.name] or 0) + 1
            end
          end
        end
      end
      local parts = {}
      for k, v in pairs(counts) do parts[#parts + 1] = k .. "=" .. v end
      table.sort(parts)
      log("[randputF][DIAG] phantom=" .. phantom .. " fluids={" .. table.concat(parts, ", ") .. "}")
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

-- (§7.5) Pose de pompe sur lac NON encore coloré : au-delà du rayon de chunks
-- générés, les tuiles de lac restent la tuile fantôme `randputf-lac-neutre` au
-- fluide marqueur `randputf-neutre`. Une pompe côtière posée dessus turbine ce
-- fluide fantôme : la turbine (input filter = fluide assigné par la seed) n'a
-- alors « pas d'entrée pour les fluides » et rien ne sort. On force donc le
-- remplissage du lac connexe au moment où le joueur pose la pompe (flood-fill
-- circonscrit autour de la pompe ; le reste se recolore à la génération).
local function color_lake_under_pump(surface, position)
  local tile = surface.get_tile(position.x, position.y)
  if tile.valid and tile.name == PHANTOM_TILE then
    local R = 128
    fill_lakes_in_area(surface, {
      left_top = { x = position.x - R, y = position.y - R },
      right_bottom = { x = position.x + R, y = position.y + R },
    })
  end
end

for _, event_id in ipairs{
  defines.events.on_built_entity,
  defines.events.on_robot_built_entity,
  defines.events.on_script_built_entity,
} do
  script.on_event(event_id, function(event)
    local entity = event.created_entity or event.entity
    if entity and entity.valid and entity.name == "offshore-pump"
      and entity.surface and entity.surface.valid
    then
      color_lake_under_pump(entity.surface, entity.position)
    end
  end, { { filter = "type", type = "offshore-pump" } })
end

script.on_event(defines.events.on_chunk_generated, function(event)
  local surface = event.surface
  if surface and surface.valid then
    process_crash_site(surface, event.area)
    -- (§7.5) Remplissage des lacs : à chaque chunk généré, chaque tuile
    -- fantôme démarre une flood-fill de son lac connexe, qui adopte le fluide
    -- d'un voisin déjà coloré (propagation inter-chunks) sinon le prochain de
    -- la seed (tourniquet).
    fill_lakes_in_area(surface, event.area)
    -- (§6.5) Gisements (items + fluides) : pose explicite des blocs/puits des
    -- patchs sur ce chunk (plus d'autoplace mapgen).
    place_patch_gisements_in_area(surface, event.area)
  end
end)

