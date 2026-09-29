-- Offline test: loads a Speed_Curves .setting as a Lua table (like Fusion does),
-- pulls the SourceTime / HUD expressions out and evaluates them for every preset
-- with a mocked SCCtrl + comp. Run from the plugin folder, after the generator:
--   lua src/Giniroisenkou_Speed_Curves_test.lua [file.setting] [out.csv]
local path = arg[1] or "build/Edit/Effects/Speed_Curves/Speed_Curves.setting"
local src = assert(io.open(path)):read("a")

-- stub the Fusion constructors so the file loads as plain data
local function ctor(kind) return function(t) t.__kind = kind; return t end end
local env = setmetatable({ ordered = function() return function(t) return t end end },
  { __index = function(_, k) return ctor(k) end })
local chunk = assert(load("return " .. src, "setting", "t", env))
local S = chunk()
local macro; for _, v in pairs(S.Tools) do macro = v end
local tools = macro.Tools
local stExpr = tools.SCTime.Inputs.SourceTime.Expression
local hudExpr = tools.SCHud.Inputs.StyledText.Expression
assert(stExpr:sub(1,1) == ":" and hudExpr:sub(1,1) == ":")

-- every InstanceInput must point at a real control / known tool
for k, v in pairs(macro.Inputs) do
  assert(tools[v.SourceOp], "bad SourceOp in " .. k)
  if v.SourceOp == "SCCtrl" and v.Source ~= "Input" then
    assert(tools.SCCtrl.UserControls[v.Source], "missing user control " .. v.Source)
  end
end

local defaults = {}
for id, uc in pairs(tools.SCCtrl.UserControls) do defaults[id] = uc.INP_Default end

local function evalExpr(expr, ctrl, t, rs, re)
  local e = setmetatable({ SCCtrl = ctrl, comp = { RenderStart = rs, RenderEnd = re }, time = t,
    Text = function(s) return s end }, { __index = _G })
  local f = assert(load(expr:sub(2), "expr", "t", e))
  return f()
end

local names = {}
for i, it in ipairs(tools.SCCtrl.UserControls.Preset) do names[#names + 1] = it.CCS_AddString:match("^(.-)%s%s%s") or it.CCS_AddString end

local rs, re = 1000, 1149 -- 150-frame clip that doesn't start at 0
local out = io.open(arg[2] or "build/curves.csv", "w")
out:write("preset,frame,source\n")
local fails = 0
for p = 0, #names - 1 do
  for _, fit in ipairs({1, 0}) do
    local c = {}; for k, v in pairs(defaults) do c[k] = v end
    c.Preset = p; c.Timing = fit
    local prev, minv, maxv = nil, 1e9, -1e9
    local first, last
    for t = rs, re do
      local v = evalExpr(stExpr, c, t, rs, re)
      assert(type(v) == "number" and v == v, "NaN preset " .. p)
      if v < rs - 1e-6 or v > re + 1e-6 then fails = fails + 1; print("OUT OF RANGE", names[p+1], t, v) end
      if fit == 1 then out:write(p, ",", t - rs, ",", v - rs, "\n") end
      first = first or v; last = v
      minv = math.min(minv, v); maxv = math.max(maxv, v)
    end
    local hud = evalExpr(hudExpr, c, rs + 40, rs, re)
    assert(type(hud) == "string")
    if fit == 1 then
      print(string.format("%-30s first=%7.2f last=%7.2f range=[%.1f..%.1f] hud@40='%s'",
        names[p+1], first - rs, last - rs, minv - rs, maxv - rs, hud))
    end
  end
end
out:close()
print(fails == 0 and "ALL OK" or ("FAILS: " .. fails))
