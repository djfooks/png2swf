import flash.Lib;
import flash.display.BitmapData;
import flash.display.Bitmap;
import flash.external.ExternalInterface;

class Main
{
    public static function main()
    {
        ExternalInterface.call("log", "start");
        Lib.current.addChild(new AAAPNGIMGSYMBOLAAA());
        ExternalInterface.call("log", "end");
    }
}
