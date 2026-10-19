// Native fresh file read only. No WebServer, WebConnection or listening socket.
// DD1's native reader uses Binaries/Web regardless of subclass IncludePath.
class APFileSnapshotReader extends WebResponse config(DD1ArchipelagoFileReader);
defaultproperties
{
    IncludePath="/Web"
}
