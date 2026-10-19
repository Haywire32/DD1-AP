// Native UI artwork imported from Assets/APLogo.tga. See Assets/LICENSE.txt.
class APShopLogo extends Object;

var Texture2D NativeIcon;

// DD1's UIDraw accepts Texture2D or MaterialInterface, not ScriptedTexture.
// A packaged static texture preserves normal clipping, hover and tooltip order.
function Surface GetIcon()
{
    return NativeIcon;
}

defaultproperties
{
    NativeIcon=Texture2D'APLogoNative.Logo'
}
