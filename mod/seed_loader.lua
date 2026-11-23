-- Charge la seed embarquée par le build. Retourne une table vide si absente.
local ok, loaded = pcall(require, "seed.seed")
if ok and type(loaded) == "table" then
  return loaded
end
return {}
