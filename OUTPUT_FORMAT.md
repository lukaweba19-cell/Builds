# Build file output format (MANDATORY)

Every build file we generate (`dragon.txt`, and any future partTable
build) MUST use exactly this format. No exceptions.

```lua
local partTable = {
    {CFrame = CFrame.new(x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22), Name = 'PartName'},
}

local previewFolder = workspace:FindFirstChild("BuildsStructures") or Instance.new("Folder", workspace)
previewFolder.Name = "BuildsStructures"

for _, v in pairs(partTable) do
    local part = game.ReplicatedStorage.ClientItemInfo:FindFirstChild(v.Name):FindFirstChildOfClass('Model'):Clone()
    part.Parent = previewFolder
    part:SetPrimaryPartCFrame(v.CFrame)
    part.Name = v.Name
    local treeValue = Instance.new("StringValue", part)
    treeValue.Name = "PurchasedBoxItemName"
    treeValue.Value = v.Name
end
```

Rules:

* `local partTable`, not `t =` and not the stolenBase format
* Each entry is `{CFrame = CFrame.new(...), Name = '...'}` only. No
  TreeValue, no color
* `CFrame.new` takes 12 numbers: x, y, z, then the 9 rotation values
* `SetPrimaryPartCFrame`, not `PivotTo`
* Parents to `BuildsStructures`
* Adds a `PurchasedBoxItemName` StringValue set to the part name
* Part names have to exist in ReplicatedStorage.ClientItemInfo
  (Floor2Large, Wall2Tall, GlassPane4, Wedge4, Post, GlassDoor1,
  Floor1Small, etc.)
* Walls that face different directions need different rotation
