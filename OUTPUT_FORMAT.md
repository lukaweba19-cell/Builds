# Build file output format (MANDATORY)

The only format that verifiably works in game is the one inside
`Musseum v1.lua.txt`. The loader there is saved byte-exact as
`tools/museum_loader.lua`; generators ship it and verifiers cross-check
it. Every build file we produce follows this.

## Entries

Every **wood** part MUST carry its wood class — that TreeValue is what
tells the blueprint which wood to use when filling the build:

```lua
local partTable = {
    {CFrame = CFrame.new(x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22), Name = 'Wall2Tall', TreeValue = 'Walnut'},
}
```

Non-wood parts (glass, etc.) get no TreeValue:

```lua
    {CFrame = CFrame.new(x, y, z, ...), Name = 'GlassPane2'},
```

## Rules

* `local partTable`, not `t =` and not the stolenBase format
* Each entry is `{CFrame = CFrame.new(...), Name = '...', TreeValue = '...'}`
* `CFrame.new` takes 12 numbers: x, y, z, then the 9 rotation values
* `SetPrimaryPartCFrame`, not `PivotTo`
* Wood part (has TreeValue) -> cloned into `workspace.Builds`, gets a
  `TreeValue` StringValue whose **value is the wood class**, and its
  `BuildDependentWood` is painted to that wood
* Non-wood part (no TreeValue) -> cloned into `workspace.BuildsStructures`,
  gets a `PurchasedBoxItemName` StringValue set to the part name
* Part names have to exist in ReplicatedStorage.ClientItemInfo
  (Floor2Large, Wall2Tall, GlassPane4, Wedge4, Post, GlassDoor1,
  Floor1Small, etc.)
* The wood class must be one the loader's colour chain handles
  (Generic, Oak, Cherry, Fir, Birch, Walnut, Koa, Volcano, GreenSwampy,
  GoldSwampy, Palm, SnowGlow, Frost, CaveCrawler, BlueSpruce, LoneCave,
  Spooky, SpookyNeon)
* Walls that face different directions need different rotation

## Why earlier variants failed

* The `Hant.txt` loader parents parts to `workspace.Base` /
  `workspace.Structures` — folders the blueprint system never scans, so
  the build "wouldn't load". Never use it.
* A structure-only loader (`BuildsStructures` + `PurchasedBoxItemName`
  for everything) loads, but carries **no wood information**, so the
  blueprint doesn't know what to fill the parts with. That format is
  only for pure structure/preview exports with no wood.
