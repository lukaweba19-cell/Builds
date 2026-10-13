local buildsFolder = workspace:FindFirstChild("Builds") or Instance.new("Folder", workspace)
buildsFolder.Name = 'Builds'

local structureFolder = workspace:FindFirstChild("BuildsStructures") or Instance.new("Folder", workspace)
structureFolder.Name = 'BuildsStructures'

for _, v in pairs(partTable) do
	local part = game.ReplicatedStorage.ClientItemInfo:FindFirstChild(v.Name):FindFirstChildOfClass('Model'):Clone()
	part.Parent = (v.TreeValue and buildsFolder or structureFolder)
	part:SetPrimaryPartCFrame(v.CFrame)
	part.Name = v.Name
	local treeValue = Instance.new("StringValue", part)
	treeValue.Name = (v.TreeValue and 'TreeValue' or 'PurchasedBoxItemName')
	treeValue.Value = v.TreeValue or v.Name

	if v.TreeValue == "Generic" then part.BuildDependentWood.Color = Color3.fromRGB(204, 142, 105) elseif v.TreeValue == "Oak" then part.BuildDependentWood.Color = Color3.fromRGB(234, 184, 146) elseif v.TreeValue == "Cherry" then part.BuildDependentWood.Color = Color3.fromRGB(163, 75, 75) elseif v.TreeValue == "Fir" then part.BuildDependentWood.Color = Color3.fromRGB(215, 197, 154) elseif v.TreeValue == "Birch" then part.BuildDependentWood.Color = Color3.fromRGB(205, 205, 205) elseif v.TreeValue == "Walnut" then part.BuildDependentWood.Color = Color3.fromRGB(105, 64, 40) elseif v.TreeValue == "Koa" then part.BuildDependentWood.Color = Color3.fromRGB(143, 76, 42) elseif v.TreeValue == "Volcano" then part.BuildDependentWood.Color = Color3.fromRGB(255, 0, 0) elseif v.TreeValue == "GreenSwampy" then part.BuildDependentWood.Color = Color3.fromRGB(52, 142, 64) elseif v.TreeValue == "GoldSwampy" then part.BuildDependentWood.Color = Color3.fromRGB(226, 155, 64) elseif v.TreeValue == "Palm" then part.BuildDependentWood.Color = Color3.fromRGB(226, 220, 188) elseif v.TreeValue == "SnowGlow" then part.BuildDependentWood.Color = Color3.fromRGB(255, 255, 0) elseif v.TreeValue == "Frost" then part.BuildDependentWood.Color = Color3.fromRGB(159, 243, 233) elseif v.TreeValue == "CaveCrawler" then part.BuildDependentWood.Color = Color3.fromRGB(16, 42, 220) elseif v.TreeValue == "BlueSpruce" then part.BuildDependentWood.Color = Color3.fromRGB(159, 173, 192) elseif v.TreeValue == "LoneCave" then part.BuildDependentWood.Color = Color3.fromRGB(248, 248, 248) elseif v.TreeValue == "Spooky" then part.BuildDependentWood.Material = Enum.Material.Granite part.BuildDependentWood.Color = Color3.fromRGB(170, 85, 0) elseif v.TreeValue == "SpookyNeon" then part.BuildDependentWood.Material = Enum.Material.Neon part.BuildDependentWood.Color = Color3.fromRGB(170, 85, 0) elseif v.TreeValue == "Birch" then part.BuildDependentWood.Color = Color3.fromRGB(163, 162, 165) end

	for _, _Part in pairs(part:GetChildren()) do
		if _Part:IsA('BasePart') and _Part.Transparency == 0 then
			_Part.Transparency = 0.3
		end
	end
end
