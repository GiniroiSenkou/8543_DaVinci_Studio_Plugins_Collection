--[=[
Giniroisenkou_Speed_Curves_testclip.lua  -  test helper (run inside DaVinci Resolve)
Workspace > Console > Lua, then:  dofile([[<plugin folder>\src\Giniroisenkou_Speed_Curves_testclip.lua]])
or copy it to  %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Edit\  and run from Workspace > Scripts.

What it does (never touches existing timeline clips):
 1. picks a random video clip from the Media Pool
 2. appends ~5 s of it to the END of the current timeline
 3. tags it with a clip colour nobody else on the timeline uses
 4. adds a Fusion comp to that new clip and wires
       MediaIn1 -> Speed_Curves -> MediaOut1
    using the .setting next to this script (Fusion-page path test).
The Edit-page path is tested by hand: drag Speed_Curves from
Effects > Fusion Effects onto the same clip (or another test clip).
]=]

local SECONDS = 5
local PRESET  = 2   -- 0 Normal, 1 Boomerang, 2 Slow-Mo Hit, ... (see README)

resolve = resolve or Resolve()
local pm = resolve:GetProjectManager()
local project = pm:GetCurrentProject()
local tl = project and project:GetCurrentTimeline()
assert(tl, "Open a project with a timeline first")
local mp = project:GetMediaPool()

-- locate the .setting beside this script
local here = debug.getinfo(1, "S").source:match("^@(.*[\\/])") or ""
local settingPath = here .. "../build/Edit/Effects/Speed_Curves/Speed_Curves.setting"  -- run the generator first

-- 1. collect video clips
local clips = {}
local function walk(folder)
  for _, c in ipairs(folder:GetClipList() or {}) do
    local t = (c:GetClipProperty("Type") or "")
    if t:find("Video") and tonumber(c:GetClipProperty("Frames") or "0") and tonumber(c:GetClipProperty("Frames") or "0") > 10 then
      clips[#clips + 1] = c
    end
  end
  for _, sub in ipairs(folder:GetSubFolderList() or {}) do walk(sub) end
end
walk(mp:GetRootFolder())
assert(#clips > 0, "No video clips in the Media Pool")
math.randomseed(os.time())
local clip = clips[math.random(#clips)]
local frames = tonumber(clip:GetClipProperty("Frames"))
local fps = tonumber(clip:GetClipProperty("FPS")) or 25
local want = math.floor(SECONDS * fps)
local startF = math.max(0, math.floor((frames - want) / 2))
local endF = math.min(frames - 1, startF + want - 1)

-- 2. colours already in use
local used = {}
for tr = 1, tl:GetTrackCount("video") do
  for _, it in ipairs(tl:GetItemListInTrack("video", tr) or {}) do used[it:GetClipColor() or ""] = true end
end
local palette = { "Pink", "Lime", "Teal", "Violet", "Apricot", "Navy", "Olive", "Purple",
                  "Tan", "Beige", "Brown", "Chocolate", "Yellow", "Green", "Blue", "Orange" }
local colour = "Pink"
for _, c in ipairs(palette) do if not used[c] then colour = c; break end end

-- 3. append at end of timeline
local items = mp:AppendToTimeline({ { mediaPoolItem = clip, startFrame = startF, endFrame = endF } })
local item = items and items[1]
assert(item, "AppendToTimeline failed")
item:SetClipColor(colour)
print(("[Speed_Curves] test clip '%s' (%d-%d) appended at %d, colour %s")
  :format(clip:GetName(), startF, endF, item:GetStart(), colour))

-- 4. Fusion-page wiring
local s = bmd.readfile(settingPath)
if not s then print("[Speed_Curves] could not read " .. settingPath .. " - skipping Fusion comp step"); return end
local fcomp = item:AddFusionComp()
assert(fcomp, "AddFusionComp failed")
fcomp:Lock()
fcomp:Paste(s)
local tool = fcomp:FindTool("Speed_Curves")
if not tool then
  for _, t in pairs(fcomp:GetToolList(false)) do
    if t:GetAttrs().TOOLS_Name:find("^Speed_Curves") then tool = t end
  end
end
local mi, mo = fcomp:FindTool("MediaIn1"), fcomp:FindTool("MediaOut1")
assert(tool and mi and mo, "wiring failed: tool/MediaIn1/MediaOut1 missing")
-- connect first image input / first output of the macro
local inp
for _, i in pairs(tool:GetInputList()) do
  if i:GetAttrs().INPS_DataType == "Image" then inp = i; break end
end
local outp = tool:GetOutputList()[1]
inp:ConnectTo(mi.Output)
mo.Input:ConnectTo(outp)
tool:SetInput("Preset", PRESET)
fcomp:Unlock()
print("[Speed_Curves] Fusion comp wired: MediaIn1 -> " .. tool:GetAttrs().TOOLS_Name .. " -> MediaOut1, preset " .. PRESET)
print("[Speed_Curves] open the Fusion page on the " .. colour .. " clip, or scrub it on the Edit page.")
